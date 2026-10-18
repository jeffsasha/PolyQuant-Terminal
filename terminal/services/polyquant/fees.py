from datetime import datetime,timezone
from decimal import Decimal as D,ROUND_HALF_EVEN,ROUND_CEILING


class FeeModel:
    coefficient=D('0.0695')
    verified_from=datetime(2026,10,16,tzinfo=timezone.utc)
    change=datetime(2026,10,19,17,tzinfo=timezone.utc)
    policy_id='us-reviewed-2026-10-16'
    @staticmethod
    def round(value): return value.quantize(D('0.01'),rounding=ROUND_HALF_EVEN)
    def exact(self,price,qty): return self.coefficient*qty*price*(1-price)
    def fees(self,fills,at):
        if at<self.verified_from: raise ValueError('Historical fee schedule is unverified')
        cumulative=D('0'); charged=D('0'); result=[]
        for fill in fills:
            exact=self.exact(fill.price,fill.qty); cumulative+=exact
            fee=min(self.round(exact),self.round(cumulative)-charged)
            result.append(fee); charged+=fee
        return result
    def maker_coefficient(self,at):
        if at<self.verified_from: raise ValueError('Historical rebate schedule is unverified')
        return D('-.0125') if at<self.change else D('0')
    def reserve_fee(self,qty):
        return (self.coefficient*qty*D('.25')).quantize(D('.01'),rounding=ROUND_CEILING)


FEE_SOURCE='https://docs.polymarket.us/fees'
