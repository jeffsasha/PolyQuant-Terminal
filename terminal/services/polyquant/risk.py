from decimal import Decimal as D
from .types import RiskDecision,DISCRETIONARY_IDS,BOT_ACCOUNT,BOT_STRATEGY,AGGRESSIVE_ACCOUNT,AGGRESSIVE_STRATEGY,BOT_PROFILES,ExperimentConfig
from .fees import FeeModel


def config_for(account_id,strategy=None):
    if (account_id,strategy)==(AGGRESSIVE_ACCOUNT,AGGRESSIVE_STRATEGY):
        return ExperimentConfig(version='aggressive-paper-v2',risk_per_trade=D('.40'),
                                exposure_limit=D('.80'),cadence_limit=D('.40'),daily_loss=D('.20'))
    return ExperimentConfig()


def committed_cost(account):
    return sum((p['cost']+p.get('fees',D('0')) for p in account.positions),D('0'))+account.reserved


def size_aggressive(account,market,book,side,limit):
    """Max affordable venue lots inside a 35% cadence / 70% total target and hard caps."""
    cfg=config_for(AGGRESSIVE_ACCOUNT,AGGRESSIVE_STRATEGY)
    committed=committed_cost(account)
    cadence=sum((p['cost']+p.get('fees',D('0')) for p in account.positions if p.get('horizon')==market.horizon),D('0'))
    cadence+=sum((p['reserved'] for p in account.pending if p.get('horizon')==market.horizon),D('0'))
    limits={'cadence_target':account.equity*D('.35')-cadence,'total_target':account.equity*D('.70')-committed,
            'per_trade_cap':account.equity*cfg.risk_per_trade,'total_cap':account.equity*cfg.exposure_limit-committed,
            'cadence_cap':account.equity*cfg.cadence_limit-cadence,'available_cash':account.cash-account.reserved}
    budget=max(D('0'),min(limits.values()))
    down=side.endswith('DOWN');source=book.bids if down else book.asks
    depth=sum(((q*D('.5')).quantize(D('.01'),rounding='ROUND_DOWN') for p,q in source if (1-p if down else p)+market.tick<=limit),D('0'))
    lot=market.minimum_qty;fees=FeeModel()
    lo=0;hi=int(min(depth,budget/limit)/lot)
    while lo<hi:
        mid=(lo+hi+1)//2;qty=lot*mid
        if qty*limit+fees.reserve_fee(qty)<=budget:lo=mid
        else:hi=mid-1
    qty=lot*lo;cost=qty*limit+fees.reserve_fee(qty)
    return {'qty':qty,'maximum_cost':cost,'budget':budget,'budget_limits':limits,
            'conservative_visible_depth':depth,'equity':account.equity,'committed_before':committed,
            'target_allocation':D('.70'),'maximum_allocation':D('.80'),
            'reasons':[] if qty>=lot else ['SIZING_BELOW_VENUE_MINIMUM']}


class RiskManager:
    def evaluate(self,intent,account,market,book,reference,config,at):
        if intent.account_id==AGGRESSIVE_ACCOUNT:config=config_for(intent.account_id,intent.strategy)
        reasons=[]; selling=intent.side.startswith('SELL_')
        discretionary=intent.account_id in DISCRETIONARY_IDS and intent.strategy=='manual_discretionary'
        experiment=intent.account_id in BOT_PROFILES and intent.strategy==BOT_PROFILES[intent.account_id]
        independent=discretionary or experiment
        if intent.side not in ['BUY_UP','BUY_DOWN','SELL_UP','SELL_DOWN']: reasons.append('INVALID_SIDE')
        if not intent.qty.is_finite() or not intent.limit.is_finite() or intent.qty<=0 or not 0<intent.limit<1:
            return RiskDecision(False,('INVALID_ORDER_VALUES',))
        if intent.qty<market.minimum_qty or intent.qty%market.minimum_qty: reasons.append('INVALID_QUANTITY_INCREMENT')
        if market.tick<=0 or intent.limit%market.tick: reasons.append('INVALID_PRICE_TICK')
        if account.halts: reasons.extend(account.halts)
        if account.cooldown_until and at<account.cooldown_until: reasons.append('LOSS_COOLDOWN')
        if not market.active or market.closed or market.status!='MARKET_STATUS_OPEN' or not market.start<=at<market.end:
            reasons.append('MARKET_NOT_OPEN')
        if not book.fresh(at): reasons.append('STALE_BOOK')
        if not book.bids or not book.asks: reasons.append('INSUFFICIENT_LIQUIDITY')
        elif book.asks[0][0]-book.bids[0][0]>config.max_spread: reasons.append('SPREAD_LIMIT')
        fee=FeeModel().reserve_fee(intent.qty)
        maximum_cost=fee if selling else intent.limit*intent.qty+fee
        if selling:
            held=sum((p['qty'] for p in account.positions if p['market_id']==market.id and p['direction']==intent.side.split('_')[-1]),D('0'))
            if held<intent.qty: reasons.append('UNCOVERED_SALE')
        else:
            if intent.account_id==AGGRESSIVE_ACCOUNT:
                if not account.valuation_ready:reasons.append('PORTFOLIO_VALUATION_UNAVAILABLE')
                if not account.risk_day_ready:reasons.append('RISK_DAY_BASELINE_UNAVAILABLE')
            if not independent:
                if not reference.validated: reasons.append('REFERENCE_RECONCILIATION_FAILED')
                elif not reference.source_at or not 0<=(at-reference.source_at).total_seconds()<=3: reasons.append('STALE_REFERENCE')
            if market.threshold is None: reasons.append('OFFICIAL_THRESHOLD_UNAVAILABLE')
            if (market.end-at).total_seconds()<={'15m':120,'1h':300}[market.horizon]: reasons.append('NO_ENTRY_WINDOW')
            if account.equity<=0 or maximum_cost>account.equity*config.risk_per_trade: reasons.append('PER_TRADE_LOSS_LIMIT')
            if account.valuation_ready and (account.risk_day_ready or intent.account_id!=AGGRESSIVE_ACCOUNT) and (account.day_start_equity<=0 or account.day_start_equity-account.equity>=account.day_start_equity*config.daily_loss):
                reasons.append('DAILY_LOSS_LIMIT')
            positions=list(account.positions); pending=list(account.pending)
            if len(positions)+len(pending)>=config.max_positions: reasons.append('POSITION_LIMIT')
            if any(p.get('horizon')==market.horizon or p['market_id']==market.id for p in positions+pending): reasons.append('CADENCE_POSITION_LIMIT')
            if any(p.get('horizon') is None for p in positions+pending): reasons.append('UNCLASSIFIED_EXISTING_EXPOSURE')
            committed=committed_cost(account)
            if committed+maximum_cost>account.equity*config.exposure_limit: reasons.append('COMBINED_EXPOSURE_LIMIT')
            cadence=sum((p['cost']+p.get('fees',D('0')) for p in positions if p.get('horizon')==market.horizon),D('0'))+sum((p['reserved'] for p in pending if p.get('horizon')==market.horizon),D('0'))
            if cadence+maximum_cost>account.equity*config.cadence_limit: reasons.append('CADENCE_EXPOSURE_LIMIT')
            if independent: pass  # Discretionary or explicitly authorized heuristic; no calibrated edge claim.
            elif intent.probability is None or not intent.probability.is_finite() or not 0<=intent.probability<=1:
                reasons.append('MODEL_PROBABILITY_UNAVAILABLE')
            elif intent.probability-intent.limit-fee/intent.qty<config.min_edge: reasons.append('INSUFFICIENT_NET_EDGE')
        if maximum_cost>account.cash-account.reserved: reasons.append('INSUFFICIENT_CAPITAL')
        return RiskDecision(not reasons,tuple(dict.fromkeys(reasons)),maximum_cost)
