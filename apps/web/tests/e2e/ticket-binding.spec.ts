import {test,expect} from '@playwright/test';
import {ticketFingerprint,previewMatches} from '../../lib/ticket';
test('a preview cannot authorize a different market, account or edited ticket',()=>{
 const ticket={account_id:'manual',market_id:'old-contract',side:'BUY_UP',qty:'1',limit:'0.50',scenario:'conservative'};
 const preview={ticketKey:ticketFingerprint(ticket)};
 expect(previewMatches(preview,ticket)).toBe(true);
 for(const field of Object.keys(ticket))expect(previewMatches(preview,{...ticket,[field]:'changed'})).toBe(false);
 expect(previewMatches(null,ticket)).toBe(false);
});
