from decimal import Decimal as D
from .types import RiskDecision
from .fees import FeeModel


class RiskManager:
    def evaluate(self,intent,account,market,book,reference,config,at):
        reasons=[]; selling=intent.side.startswith('SELL_')
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
            if not reference.validated: reasons.append('REFERENCE_RECONCILIATION_FAILED')
            elif not reference.source_at or not 0<=(at-reference.source_at).total_seconds()<=3: reasons.append('STALE_REFERENCE')
            if market.threshold is None: reasons.append('OFFICIAL_THRESHOLD_UNAVAILABLE')
            if (market.end-at).total_seconds()<={'15m':120,'1h':300}[market.horizon]: reasons.append('NO_ENTRY_WINDOW')
            if account.equity<=0 or maximum_cost>account.equity*config.risk_per_trade: reasons.append('PER_TRADE_LOSS_LIMIT')
            if account.day_start_equity<=0 or account.day_start_equity-account.equity>=account.day_start_equity*config.daily_loss:
                reasons.append('DAILY_LOSS_LIMIT')
            positions=list(account.positions); pending=list(account.pending)
            if len(positions)+len(pending)>=config.max_positions: reasons.append('POSITION_LIMIT')
            if any(p.get('horizon')==market.horizon or p['market_id']==market.id for p in positions+pending): reasons.append('CADENCE_POSITION_LIMIT')
            if any(p.get('horizon') is None for p in positions+pending): reasons.append('UNCLASSIFIED_EXISTING_EXPOSURE')
            committed=sum((p['cost'] for p in positions),D('0'))+account.reserved
            if committed+maximum_cost>account.equity*config.exposure_limit: reasons.append('COMBINED_EXPOSURE_LIMIT')
            cadence=sum((p['cost'] for p in positions if p.get('horizon')==market.horizon),D('0'))+sum((p['reserved'] for p in pending if p.get('horizon')==market.horizon),D('0'))
            if cadence+maximum_cost>account.equity*config.cadence_limit: reasons.append('CADENCE_EXPOSURE_LIMIT')
            if intent.probability is None or not intent.probability.is_finite() or not 0<=intent.probability<=1:
                reasons.append('MODEL_PROBABILITY_UNAVAILABLE')
            elif intent.probability-intent.limit-fee/intent.qty<config.min_edge: reasons.append('INSUFFICIENT_NET_EDGE')
        if maximum_cost>account.cash-account.reserved: reasons.append('INSUFFICIENT_CAPITAL')
        return RiskDecision(not reasons,tuple(dict.fromkeys(reasons)),maximum_cost)
