export interface TicketFields {account_id:string;market_id:string;side:string;qty:string;limit:string;scenario:string}
export function ticketFingerprint(ticket:TicketFields){return JSON.stringify([ticket.account_id,ticket.market_id,ticket.side,ticket.qty,ticket.limit,ticket.scenario]);}
export function previewMatches(preview:{ticketKey?:string}|null,ticket:TicketFields){return !!preview&&preview.ticketKey===ticketFingerprint(ticket);}
