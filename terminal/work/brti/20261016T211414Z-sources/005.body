> ## Documentation Index
> Fetch the complete documentation index at: https://docs.polymarket.us/llms.txt
> Use this file to discover all available pages before exploring further.

# Changelog

> Updates and Announcements for all APIs, tagged and filterable

### Subscribe to all Changes:

* Add to any RSS reader using the URL: `https://docs.polymarket.us/changelog/rss.xml`
* Slack has a built-in reader: use `/feed subscribe https://docs.polymarket.us/changelog/rss.xml`

<Update label="October 12, 2026" description="Upcoming: tiered maker and taker rebates" tags={["Upcoming", "Incentives", "Institutional API", "Retail API"]} rss={{ title: "Maker and taker rebates move to volume tiers at 1:00 PM ET on Monday, October 19, 2026", description: "From 1:00 PM ET on October 19 the maker rebate coefficient moves from a flat -0.0125 to tiers set by prior calendar-month maker volume (maker Tier 1 below $10M: no rebate; Tier 2 from $10M: -0.0035; Tier 3 from $50M: -0.0070; Tier 4 from $200M: -0.0104), and taker rebates move to six tiers (Tier 1 below $250K: no rebate; Tier 2 to Tier 6: 3%, 5%, 10%, 15% and 30% of taker fees paid at $250K, $1M, $10M, $25M and $50M). For the October 19 launch only, each tier is the higher of September volume or 4x October 12 to 18 volume. The additional weekly crypto maker rebate ends at 8:00 AM ET on October 15. Taker fees are unchanged." }}>
  Effective **1:00 PM ET on Monday, October 19, 2026**, maker and taker rebates move to tiers set by your trading volume. Taker fees are unchanged. See [Rebate changes effective October 19, 2026](/fees#rebate-changes-effective-october-19-2026) on the Fee Schedule for the full rules and how volume is measured.

  * **Maker rebates:** the maker rebate coefficient moves from a flat `-0.0125` to four tiers set by your prior calendar-month maker volume: Tier 1 below \$10M (no maker rebate), Tier 2 `-0.0035` from \$10M, Tier 3 `-0.0070` from \$50M and Tier 4 `-0.0104` from \$200M. Rebates are still credited at the point of trade. Combo fills continue to carry no maker rebate.
  * **Taker rebates:** six tiers set by your prior calendar-month taker volume: Tier 1 below \$250K (no rebate), Tier 2 3% (\$250K to \$1M), Tier 3 5% (\$1M to \$10M), Tier 4 10% (\$10M to \$25M), Tier 5 15% (\$25M to \$50M) and Tier 6 30% (\$50M+) of taker fees paid. Rebates continue to be paid out weekly.
  * **Crypto maker rebates:** the additional 17% weekly crypto maker rebate ends at **8:00 AM ET on Thursday, October 15, 2026**. From 8:00 AM ET on October 15 until 1:00 PM ET on October 19, crypto makers receive the standard `-0.0125` rebate. From 1:00 PM ET on October 19, crypto markets use the maker tiers above.
  * **How tiers are set:** maker and taker tiers are numbered separately from Tier 1 (lowest volume) upward. For the October 19 launch only, each tier is the higher of your September 2026 volume or 4x your October 12 to 18 volume. From November 1, tiers reset on the first of each month based on the prior calendar month's volume. Your current tiers and rebates apply until 1:00 PM ET on October 19.
  * **Volume** is contracts × the price of the side you received: buying at \$0.30 counts \$0.30 per contract, selling at \$0.30 counts \$0.70 per contract. Combo fills count toward both maker and taker volume. Voided fills are excluded.
</Update>

<Update label="October 9, 2026" description="Upcoming: primary markets on event lists" tags={["Breaking Change", "Upcoming", "Retail API"]} rss={{ title: "Event list responses change Thursday, October 15, 2026", description: "Event lists will return primary markets. Event detail endpoints by ID or slug will provide the full market set." }}>
  Effective **Thursday, October 15, 2026**, these endpoints will return only the primary market set in each event's `markets` array:

  * `GET /v1/events`
  * `GET /v2/leagues/{slug}/events`
  * `GET /v2/sports/{slug}/events`

  Primary markets are the main winner outcomes. Soccer game-to-advance markets take precedence when present. Spreads, totals, and player props will no longer accompany a primary market in list responses. Events without a primary market will retain all eligible markets.

  **Migration:** For the full market set, request `GET /v1/events/{id}` or `GET /v1/events/slug/{slug}`. Use the `id` or `slug` from the list response. See the [Events API](/api-reference/events/overview).
</Update>

<Update label="October 1, 2026" description="General access to RFQs and combos" tags={["New Feature", "Retail API"]} rss={{ title: "RFQs and combos are generally available on the Retail API", description: "RFQs and combos are available to all Retail API users with existing API keys." }}>
  * [RFQs](/api-reference/rfqs/overview) and [combos](/api-reference/combos/overview) are now available to all Retail API users with existing API keys.
</Update>

<Update label="October 1, 2026" description="RFQ quote replacement IDs" tags={["Breaking Change", "Institutional API", "Retail API"]} rss={{ title: "CreateQuote returns a new ID on replacement", description: "CreateQuote no longer preserves quoteId on replacement. Use the returned ID for deletion and the accepted quote's ID for confirmation." }}>
  * `CreateQuote` now returns a new `quoteId` on every successful call, including replacements.
  * Use the returned ID to delete the new quote. Confirm or decline using the ID in the acceptance event. See the [Institutional](/institutional/rfqs/overview#create-or-replace-a-quote) and [Retail](/api-reference/rfqs/overview#replace-a-quote) RFQ docs.
</Update>

<Update label="September 29, 2026" description="v0.0.93" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.93 - MLB inning-total markets, listing today for the MLB playoffs", description: "Nine new MLB inning-total sports market types list today with the MLB playoffs: baseball_team_inning1_total through baseball_team_inning9_total. Each inning has an Over/Under on combined runs at 0.5 and 1.5. Derive the inning number from market_sport_type rather than parsing the instrument ID. The outcome_type is totals." }}>
  * **Nine new MLB inning-total sports market types, listing today with the MLB playoffs:** `baseball_team_inning1_total` through `baseball_team_inning9_total`.
  * **Two lines per inning:** Over/Under on the combined runs scored by both teams in that inning, at `outcome_strike` `0.5` and `1.5`.
  * **Inning number:** derive it from the `market_sport_type` value rather than parsing the instrument ID.
  * **Outcome type:** `totals`.
</Update>

<Update label="September 21, 2026" description="v0.0.92" tags={["Preprod", "Upcoming", "New Feature", "Documentation", "Institutional API", "Retail API"]} rss={{ title: "v0.0.92 - Crypto price markets documented: Up/Down, Above/Below, Price Range, One-Touch (preprod)", description: "Four automated Bitcoin market families settle on CF Benchmarks' BRTI index and are listed in preprod ahead of production. New Crypto Schema page documents the identifying instrument fields (crypto_market_type, crypto_horizon, interval_start/interval_end, outcome_strike, price_to_beat, crypto_range_*, crypto_hit_direction, crypto_settlement_price). The Retail API exposes the same terms as assetPriceTerms and index price history at GET /v1/asset-prices/history. Crypto FAQs cover settlement statistics, ties, timing and maintenance. Existing hand-listed year-end Bitcoin markets carry none of these fields." }}>
  * **Crypto price markets are documented ahead of their production listing.** Four automated Bitcoin market families settle on CF Benchmarks' Bitcoin Real-Time Index (`BRTI`): 15-minute and 60-minute **Up/Down** windows, hourly, daily and weekly **Above/Below** ladders, **Price Range** ladders on the same expiries, and monthly **One-Touch** ladders. They are listed in preprod today and reach production on the schedule announced here.
  * **Institutional API:** the new [Crypto Schema](/trader-guide/crypto-schema) page documents the identifying fields. Map on `crypto_market_type` (`updown`, `strike`, `range`, `hit`) and read the window from `interval_start` / `interval_end`, the threshold from `outcome_strike` or `crypto_range_lower` / `crypto_range_upper`, the Up/Down open value from `price_to_beat`, and the settled value from `crypto_settlement_price`. Filter reference data with `eventCategory=CRY` or `clearingSym=CPC-BTC`.
  * **Retail API:** markets carry a typed [`assetPriceTerms`](/api-reference/market/overview#crypto-price-market-fields) object with the same terms, and the new [Asset Prices API](/api-reference/asset-prices/overview) serves BRTI candles from `GET /v1/asset-prices/history`. Automated crypto markets have an empty `marketType`; identify them from `assetPriceTerms.marketType`.
  * **Settlement rules** are summarised in the new [Crypto FAQs](/faqs/crypto-faqs): Up/Down, Above/Below and Price Range settle on the simple average of the 60 one-second index prices from 59 seconds before the settlement instant up to and including it (a flat Up/Down window settles Up; a value equal to a strike settles Yes); One-Touch settles on a rolling 60-second 20% trimmed mean and may settle early.
  * **Existing hand-listed year-end Bitcoin markets are unchanged.** They carry none of the `crypto_*` fields, show `marketType: "futures"` and `assetPriceTerms: null`, and state their statistic in the market rules. The Data Guide's crypto examples now use real identifiers.
</Update>

<Update label="September 19, 2026" description="Streaming best practices" tags={["Documentation", "Institutional API"]} rss={{ title: "Streaming best practices for gRPC Drop Copy", description: "New page: one long-lived Drop Copy stream per firm, persist resume_token after apply, do not cancel mid-replay. Concurrent stream cap is 20 pooled." }}>
  * **New [Streaming Best Practices](/streaming-endpoints/streaming-best-practices) page.** One long-lived `CreateDropCopySubscription` per firm and environment. Persist `resume_token` after you apply the batch. Do not put a short deadline on the streaming RPC and reconnect — that restarts replay and never catches up. Drop Copy has no per-order stream.
  * **20 concurrent gRPC streams per firm**, pooled across stream types. Market data is still 1000 symbols per stream; `CreateOrderSubscription` is not. Full table: [Rate Limits](/trader-guide/rate-limits#grpc-streaming).
</Update>

<Update label="September 17, 2026" description="v0.0.91" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.91 - One-off maintenance window Friday, September 18, 5:00am-7:00am ET", description: "A one-off maintenance window is scheduled for Friday, September 18 from 5:00am-7:00am ET, outside the normal recurring maintenance schedule. The window will affect both the Institutional API and Retail API. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Friday, September 18, 5:00am–7:00am ET.** Affects both the Institutional API and Retail API. Please note the schedule change, as this is outside our normal recurring maintenance schedule.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="September 15, 2026" description="v0.0.91" tags={["Documentation", "New Feature", "Incentives", "Institutional API", "Retail API"]} rss={{ title: "v0.0.91 - Liquidity Incentive Program: Max Spread parameter", description: "The Liquidity Incentive Program gains an optional per-program Max Spread. Where a program sets one, a second scores only when both sides of the book reach Target Size and each side's size-adjusted price sits within the Max Spread of the midpoint between the two size-adjusted prices; otherwise nobody is paid for that second. No live program sets a Max Spread yet. The public incentives API (GET /v1/incentives, Retail and Institutional) returns it as timePeriods[].maxSpread in price dollars (0.035 = 3.5¢), omitted when a program has none; programs that adopt one show the same value in cents on polymarket.us/rewards." }}>
  * **New parameter: Max Spread.** Where a program sets one, every second the exchange walks both sides of the book to Target Size and requires each side's size-adjusted price to sit within the Max Spread of the midpoint between the two size-adjusted prices. This is a test of the book, not of each trader: you do not have to quote both sides yourself. Max Spread is a half-width: a 3.5¢ Max Spread allows the two size-adjusted prices to be up to 7¢ apart. If they sit farther apart than that, or either side never reaches Target Size, nobody is paid for that second — including any side that did reach Target Size. Once a second qualifies, a one-sided quote still earns on the side it rests on. Forfeited seconds still count toward the time period and are not redistributed. Programs without a Max Spread score each side independently, exactly as today. See [What is Max Spread?](/incentives/liquidity#what-is-max-spread).
  * **No live program sets a Max Spread yet.** When a program adopts one, its Max Spread is published alongside the program's other parameters on [polymarket.us/rewards](https://polymarket.us/rewards) and in `GET /v1/incentives` (`timePeriods[].maxSpread`).
  * **Retail and Institutional APIs:** `GET /v1/incentives` now includes `timePeriods[].maxSpread` for liquidity programs that set a Max Spread, in price dollars (`0.035` = 3.5¢). It is the half-width: how far each side's size-adjusted price may sit from the midpoint between the two. The field is omitted — never `0` — when a program has no Max Spread. See the [Retail](/api-reference/incentives/overview) and [Institutional](/institutional/incentives/overview) Incentives API references.
</Update>

<Update label="September 13, 2026" description="v0.0.90" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.90 - One-off maintenance window Monday, September 14, 5:00am-8:00am ET", description: "A one-off maintenance window is scheduled for Monday, September 14 from 5:00am-8:00am ET, outside the normal recurring maintenance schedule. The window will affect both the Institutional API and Retail API. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Monday, September 14, 5:00am–8:00am ET.** Affects both the Institutional API and Retail API. Please note the schedule change, as this is outside our normal recurring maintenance schedule.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="September 13, 2026" description="v0.0.89" tags={["Breaking Change", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.89 - DAY orders will not automatically cancel at 5pm during trade day rolls", description: "Day orders will cancel not auto-cancel on 9/13 during traded day roll. The Exchange team is working on improving the DAY order types performance. While the Exchange makes improvement, DAY orders will not automatically cancel at 5pm during trade day rolls. Please use GTD orders with the desired timestamp. GTD orders will remain functional with the good-til-time specified." }}>
  * **Day orders will cancel not auto-cancel on 9/13 during traded day roll.**
  * **Why:** the Exchange team is working on improving the DAY order types performance. While the Exchange makes improvement, DAY orders will not automatically cancel at 5pm during trade day rolls.
  * **Action required:** please use GTD orders with the desired timestamp. GTD orders will remain functional with the good-til-time specified.
</Update>

<Update label="September 10, 2026" description="v0.0.88" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.88 - One-off maintenance window Friday, September 11, 4:00am-7:00am ET", description: "A one-off maintenance window is scheduled for Friday, September 11 from 4:00am-7:00am ET, outside the normal recurring maintenance schedule. The window will affect both the Institutional API and Retail API. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Friday, September 11, 4:00am–7:00am ET.** Affects both the Institutional API and Retail API. Please note the schedule change, as this is outside our normal recurring maintenance schedule.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="September 9, 2026" description="v0.0.87" tags={["New Feature", "Documentation", "Institutional API", "Retail API"]} rss={{ title: "v0.0.87 - 8 additional football market types", description: "Eight additional football sports market types are documented: passing attempts, passing completions, rushing attempts, longest rush, longest reception, a player to score their team's first touchdown, a selected team's fourth-down conversions total, and the nine-outcome halftime/full-time double result. The Sports Schema inventory now matches the current football types registered by the exchange. Read the exact market from sportsMarketType on Retail or market_sport_type on Institutional data." }}>
  * **Eight additional football sports market types are now documented:**
    * **Player props:** `football_player_passing_attempts`, `football_player_passing_completions`, `football_player_rushing_attempts`, `football_player_longest_rush`, and `football_player_longest_reception`
    * **First touchdown for a team:** `football_player_team_first_touchdown` identifies whether a player scores the selected team's first touchdown. Rushing, receiving, and return touchdowns count; passing touchdowns do not.
    * **Selected-team total:** `football_team_total_fourth_down_conversions`
    * **Game outcome:** `football_game_double_result` combines the first-half result and final-game result into nine mutually exclusive outcomes.
  * **Identify the market from structured metadata:** Retail uses `sportsMarketType`; Institutional uses `market_sport_type`.
  * See [Sports Schema](/trader-guide/sports-schema) for the complete inventory and football metadata profiles.
</Update>

<Update label="September 8, 2026" description="v0.0.86" tags={["New Feature", "Documentation", "Institutional API", "Retail API"]} rss={{ title: "v0.0.86 - 71 additional sports market types documented: football, baseball, esports, table tennis, boxing, darts, pickleball, lacrosse", description: "The Sports Schema market_sport_type inventory now matches the full set of sports market types registered by the exchange: 71 sport-specific values are added. Football adds player props, combined and selected-team totals, game outcomes such as race to X points, and the live next-touchdown and next-field-goal markets (registered, not yet listed); baseball adds baseball_player_rbis, baseball_player_stolen_bases, and baseball_team_total_runs; esports adds 24 series, map, and game lines; table tennis, boxing, darts, pickleball, and lacrosse winners are added. The generic values moneyline, spreads, totals, and drawable_outcome are documented as valid values. Some values are registered ahead of their first listing. Read the exact market from sportsMarketType on Retail or market_sport_type on Institutional data." }}>
  * **71 additional sports market types are now documented.** The `market_sport_type` inventory on [Sports Schema](/trader-guide/sports-schema) now matches the full set of sports market types registered by the exchange. Some values are already listed; others are registered ahead of their first listing. Treat every value in the inventory as one that can appear on an instrument. Instruments with no sport-specific value show their `outcome_type` value in the Retail `sportsMarketType` field (for example `futures`); see the new Generic Values section.
  * **Football (35 values):**
    * **Player props:** `football_player_receptions`, `football_player_passer_rating`, `football_player_interceptions_thrown`, `football_player_sacks`, `football_player_defensive_interceptions`, `football_player_field_goals_made`, `football_player_50_plus_yard_field_goals_made`, `football_player_fantasy_points_ppr`, and `football_player_scrimmage_yards`, plus the yes/no props `football_player_first_touchdown`, `football_player_most_passing_yards`, `football_player_most_rushing_yards`, and `football_player_most_receiving_yards`.
    * **Combined game totals:** passing and rushing touchdowns, passing and rushing yards, offensive yards, turnovers, defensive interceptions, fourth-down conversions, and a successful two-point conversion yes/no. `football_game_total_pass_yards` and `football_game_total_pass_touchdowns` are also reserved for combined receiving yards and receiving touchdowns.
    * **Selected-team totals:** `football_team_total_offensive_yards`, `football_team_total_first_downs`, and `football_team_total_defensive_special_teams_touchdowns`.
    * **Game outcomes:** `football_game_last_score`, `football_game_last_touchdown`, `football_game_race_to_points` (`outcome_strike` carries the points target; each target has three legs: away team, home team, Neither Team), `football_game_highest_scoring_quarter`, `football_game_possession_winner`, `football_game_tie`, `football_game_safety`, and `football_game_onside_kick_attempt`.
    * **Live in-game markets (registered, not yet listed):** `football_next_team_touchdown` and `football_next_team_field_goal`. When these list, each touchdown or field-goal number is one three-leg product (each team plus No TD or No FG); the first instance lists at kickoff and a new instance lists after each touchdown or made field goal.
  * **Baseball (3 values):** the player props `baseball_player_rbis` and `baseball_player_stolen_bases`, and the selected-team total `baseball_team_total_runs`.
  * **Esports (24 values):** series handicaps and totals (`esports_series_map_handicap`, `esports_series_total_maps`, `esports_series_game_handicap`, `esports_series_total_games`); per-map rounds handicap and total rounds for maps 1–4; per-game first blood, total kills, and kills odd/even for games 1–4. Map markets apply to round-based titles such as Counter-Strike 2 and Valorant; game markets apply to series-of-games titles such as League of Legends and Dota 2.
  * **New sports (9 values):** `boxing_match_winner`, `darts_match_winner`, `pickleball_match_winner`, `lacrosse_team_full_game_winner`, and table tennis (`table_tennis_match_winner` plus `table_tennis_set_1_winner` through `table_tennis_set_4_winner`).
  * **Generic values:** `moneyline`, `spreads`, `totals`, and `drawable_outcome` are documented as valid `market_sport_type` values. They have the same structure as the matching `outcome_type` value and appear on instruments that carry no sport-specific value, such as instruments created before the sport-specific values existed or hand-listed markets.
  * **Identify the market from structured metadata:** Retail uses `sportsMarketType`; Institutional uses `market_sport_type`. See [Sports Schema](/trader-guide/sports-schema) for the full inventory, the esports map/game note, and the football metadata profiles.
</Update>

<Update label="September 8, 2026" description="v0.0.85" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.85 - One-off maintenance window Wednesday, September 9, 3:00am-7:00am ET", description: "A one-off maintenance window is scheduled for Wednesday, September 9 from 3:00am-7:00am ET, outside the normal recurring maintenance schedule. The window will affect both the Institutional API and Retail API. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Wednesday, September 9, 3:00am–7:00am ET.** Affects both the Institutional API and Retail API. Please note the schedule change, as this is outside our normal recurring maintenance schedule.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="September 7, 2026" description="v0.0.84" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.84 - One-off maintenance window Tuesday, September 8, 2:00am-6:00am ET", description: "A one-off maintenance window is scheduled for Tuesday, September 8 from 2:00am-6:00am ET, outside the normal recurring maintenance schedule. The window will affect both the Institutional API and Retail API. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Tuesday, September 8, 2:00am–6:00am ET.** Affects both the Institutional API and Retail API. Please note the schedule change, as this is outside our normal recurring maintenance schedule.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="September 4, 2026" description="v0.0.83" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.83 - One-off maintenance windows Saturday, September 5 and Sunday, September 6, 2:00am-6:00am ET", description: "Two one-off maintenance windows are scheduled for Saturday, September 5 and Sunday, September 6 from 2:00am-6:00am ET, outside the normal recurring maintenance schedule. The windows will affect both the Institutional API and Retail API. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance windows — Saturday, September 5, 2:00am–6:00am ET, and Sunday, September 6, 2:00am–6:00am ET.** Affects both the Institutional API and Retail API. Please note the schedule change, as these are outside our normal recurring maintenance schedule.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="September 1, 2026" description="v0.0.82" tags={["Breaking Change", "Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.82 - One-off maintenance window Wednesday, September 2, 2:00am-8:00am ET", description: "A one-off maintenance window is scheduled for Wednesday, September 2 from 2:00am-8:00am ET, outside the normal recurring maintenance schedule. The window will affect both the Institutional API and Retail API. During the window, we archive the stored execution history. After maintenance, queries for pre-maintenance executions return empty results. Export and retain any execution data you need before the window begins. To retrieve every page, pass each nextPageToken value back as pageToken until the response returns eof: true. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Wednesday, September 2, 2:00am–8:00am ET.** Affects both the Institutional API and Retail API. Please note the time change, as this is different than our normal hours.
  * **Execution history reset:** we archive the stored execution history during the maintenance window. After maintenance, queries for pre-maintenance executions return empty results.
  * **Action required:** export and retain any execution data you need before the window begins. To retrieve every page, pass each `nextPageToken` value back as `pageToken` until the response returns `eof: true`.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="August 31, 2026" description="v0.0.81" tags={["Breaking Change", "Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.81 - One-off maintenance window Tuesday, September 1, 2:00am-7:00am ET", description: "A one-off maintenance window is scheduled for Tuesday, September 1 from 2:00am-7:00am ET, outside the normal recurring maintenance schedule. The window will affect both the Institutional API and Retail API. During the window, we archive the stored execution history. After maintenance, queries for pre-maintenance executions return empty results. Export and retain any execution data you need before the window begins. To retrieve every page, pass each nextPageToken value back as pageToken until the response returns eof: true. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Tuesday, September 1, 2:00am–7:00am ET.** Affects both the Institutional API and Retail API. Please note the time change, as this is different than our normal hours.
  * **Execution history reset:** we archive the stored execution history during the maintenance window. After maintenance, queries for pre-maintenance executions return empty results.
  * **Action required:** export and retain any execution data you need before the window begins. To retrieve every page, pass each `nextPageToken` value back as `pageToken` until the response returns `eof: true`.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="August 29, 2026" description="v0.0.80" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.80 - 16 additional football game and team market types", description: "Sixteen additional football sports market types are being listed with college football (CFB) games: first-half first touchdown; game-event markets for pick six, kickoff/punt return touchdown, and overtime; a combined game touchdowns total; and selected-team statistical totals for passing/rushing touchdowns and yards, scrimmage yards, receptions, takeaways, defensive interceptions, sacks, field goals made, and 40+ yard field goals made. The team passing yards and passing touchdowns types are also used for receiving yards and receiving touchdowns. Read the exact market from sportsMarketType on Retail or market_sport_type on Institutional data." }}>
  * **16 additional football sports market types are being listed** with college football (CFB) games, covering:
    * **First touchdown:** `football_game_first_half_first_touchdown`, joining the existing full-game and second-half variants
    * **Game events:** `football_game_pick_six`, `football_game_kickoff_punt_return_touchdown`, and `football_game_overtime`
    * **Game totals:** `football_game_total_touchdowns` (combined across both teams)
    * **Selected-team statistical totals:** passing and rushing touchdowns, passing and rushing yards, scrimmage yards, receptions, takeaways, defensive interceptions, sacks, field goals made, and 40+ yard field goals made
  * **Receiving markets reuse the passing types:** `football_team_total_pass_yards` is also used for team receiving yards, and `football_team_total_pass_touchdowns` for team receiving touchdowns.
  * **Identify the market from structured metadata:** Retail uses `sportsMarketType`; Institutional uses `market_sport_type`.
  * See [Sports Schema](/trader-guide/sports-schema) for the full `market_sport_type` inventory and football metadata profiles.
</Update>

<Update label="August 26, 2026" description="v0.0.79" tags={["Breaking Change", "Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.79 - One-off maintenance extension Thursday, August 27, 2:00am-8:00am ET", description: "This week's recurring maintenance window on Thursday, August 27 will run from 2:00am-8:00am ET, a one-off extension to 8:00am. Normal recurring maintenance hours are unchanged. The window affects both the Institutional API and Retail API. We clear the stored execution history during the maintenance window. Queries for pre-maintenance executions return empty results afterwards. Pull and store the execution data you need before the window opens. Please use pagination: follow the nextPageToken value (sent as pageToken) until the response returns eof: true. View live status at https://status.polymarketexchange.com." }}>
  * **One-off maintenance extension — Thursday, August 27, 2:00am–8:00am ET.** This week's recurring maintenance window will be extended to 8:00am ET. Normal recurring maintenance hours are unchanged. Affects both the Institutional API and Retail API.
  * **Execution history reset:** we clear the stored execution history during the maintenance window. Queries for pre-maintenance executions return empty results afterwards.
  * **Action required:** pull and store the execution data you need before the window opens. Please use pagination: follow the `nextPageToken` value (sent as `pageToken`) until the response returns `eof: true`.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="August 24, 2026" description="v0.0.78" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.78 - One-off maintenance window Tuesday, August 25, 2:00am-8:00am ET", description: "FYI: a one-off maintenance window is scheduled for Tuesday, August 25 from 2:00am-8:00am ET, affecting both the Institutional API and Retail API. Please note the time change as this is different than our normal hours. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Tuesday, August 25, 2:00am–8:00am ET.** Affects both the Institutional API and Retail API. Please note the time change, as this is different than our normal hours.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="August 10, 2026" description="v0.0.77" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.77 - One-off maintenance window Tuesday, August 11, 6:00am-10:00am ET", description: "FYI: a one-off maintenance window is scheduled for Tuesday, August 11 from 6:00am-10:00am ET, affecting both the Institutional API and Retail API. Please note the time change as this is different than our normal hours. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Tuesday, August 11, 6:00am–10:00am ET.** Affects both the Institutional API and Retail API. Please note the time change, as this is different than our normal hours.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="August 5, 2026" description="v0.0.76" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.76 - 50 NFL game, team, and player market types", description: "Fifty NFL sports market types are being listed across primary game lines, period winners and spreads, game and team totals, exact margin and first-score markets, both-teams-to-score markets, statistical touchdown totals, and five player props. Read the exact market from sportsMarketType on Retail or market_sport_type on Institutional data. Player props include touchdowns from scrimmage, rushing yards, passing yards, receiving yards, and passing touchdowns." }}>
  * **50 NFL sports market types are being listed**, covering:
    * **Primary game lines:** full-game winner, spread, and total
    * **Period markets:** first/second-half and first-through-fourth-quarter winners, spreads, and combined-points totals
    * **Team totals:** full-game and first/second-half selected-team points
    * **Margin and first score:** exact margin; first score by game or half; first touchdown by full game or second half
    * **Both teams to score:** any points by half or quarter, and a touchdown by full game, half, or quarter
    * **Statistical touchdown totals:** combined defensive/special-teams touchdowns and selected-team total touchdowns
    * **Player props:** touchdowns from scrimmage (passing touchdowns excluded), rushing yards, passing yards, receiving yards, and passing touchdowns
  * **Identify the market from structured metadata:** Retail uses `sportsMarketType`; Institutional uses `market_sport_type`. All secondary game and player markets use `outcome_type=props`; player markets also use `prop_type=player`.
  * **Market identity:** use `event_external_id_sportradar`, `market_sport_type`, `long_participant_id`, `short_participant_id`, and `outcome_strike` as the canonical lookup and deduplication key. Participant IDs can be empty for game-wide totals; also use `external_participant_id` when resolving a player.
  * See [Sports Schema](/trader-guide/sports-schema) for the complete 50-type inventory and football metadata profiles.
</Update>

<Update label="July 29, 2026" description="v0.0.75" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.75 - Scheduled maintenance window Thursday, July 30, 2:00am-4:00am ET", description: "A scheduled maintenance window is set for Thursday, July 30 from 2:00am-4:00am ET, affecting both the Institutional API and Retail API. View live status at https://status.polymarketexchange.com." }}>
  * **Scheduled maintenance window — Thursday, July 30, 2:00am–4:00am ET.** Affects both the Institutional API and Retail API.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="July 29, 2026" description="v0.0.74" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.74 - MLB inning-winner markets", description: "Nine new MLB inning-winner sports market types are available: BASEBALL_TEAM_INNING1_WINNER through BASEBALL_TEAM_INNING9_WINNER. Derive the inning number from the market_sport_type enum rather than parsing the instrument ID. Each inning has three outcomes: home team, away team, and draw. Instrument IDs use atc-<game-slug>-i<inning>-<team-abbreviation|draw>; doubleheaders include -dh1 or -dh2 before the inning suffix. The outcome_type is Props." }}>
  * **Nine new MLB inning-winner sports market types:** `BASEBALL_TEAM_INNING1_WINNER` through `BASEBALL_TEAM_INNING9_WINNER`.
  * **Inning number:** derive it from mapping the `market_sport_type` enum rather than parsing the instrument ID.
  * **Three outcomes per inning:** home team, away team, and draw.
  * **Instrument ID format:** `atc-<game-slug>-i<inning>-<team-abbreviation|draw>`.
  * **Doubleheaders:** IDs include `-dh1` or `-dh2` before the inning suffix.
  * **Outcome type:** `Props`.
</Update>

<Update label="July 28, 2026" description="v0.0.73" tags={["Preprod", "Maintenance", "Upcoming", "Institutional API"]} rss={{ title: "v0.0.73 - [PREPROD ONLY] Scheduled preprod maintenance window Tuesday, July 29, 8:00am-10:00am ET - production unaffected", description: "The preprod environment will be placed into maintenance mode on Tuesday, July 29 from 8:00am-10:00am ET (about 2 hours) for scheduled database maintenance. Expect preprod FIX sessions to disconnect and preprod Institutional API requests to be rejected during the window. Production is NOT affected. No action needed; reconnect and resume testing once the window closes." }}>
  * **Preprod maintenance window — Tuesday, July 29, 8:00am–10:00am ET (\~2 hours).** The preprod environment will be placed into maintenance mode for scheduled database maintenance.
  * **Preprod only — production is not affected.**
  * During the window, preprod FIX sessions will disconnect and preprod Institutional API requests will be rejected.
  * No action needed — reconnect and resume testing once the window closes.
</Update>

<Update label="July 24, 2026" description="v0.0.72" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.72 - Scheduled maintenance window Saturday, July 25, 2:00am-4:00am ET", description: "A scheduled maintenance window is set for Saturday, July 25 from 2:00am-4:00am ET, affecting both the Institutional API and Retail API. View live status at https://status.polymarketexchange.com." }}>
  * **Scheduled maintenance window — Saturday, July 25, 2:00am–4:00am ET.** Affects both the Institutional API and Retail API.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="July 20, 2026" description="v0.0.71" tags={["New Feature", "Institutional API"]} rss={{ title: "v0.0.71 - New instrument metadata fields: home_team_name, away_team_name, tournament_name", description: "Sports instruments now carry three new metadata fields in Institutional instrument reference data: home_team_name and away_team_name (display names of the true home and away sides, independent of long/short ordering) and tournament_name (human-readable competition name, e.g. MLS, NBA, LEC Summer 2026, UFC 320, or the golf tournament name). Read them from the metadata map on SearchInstruments / GetInstrument. All newly created sports instruments carry the fields; instruments created before this change do not, so treat them as optional keys when reading." }}>
  * **Three new instrument metadata fields on sports instruments.** The `metadata` map returned by `SearchInstruments` / `GetInstrument` now includes:
    * `home_team_name` — display name of the home side (e.g., "Kansas City Chiefs")
    * `away_team_name` — display name of the away side (e.g., "Buffalo Bills")
    * `tournament_name` — human-readable competition name (e.g., "MLS", "NBA", "MLB")
  * **Home/away is independent of long/short.** `long_participant_id` / `short_participant_id` ordering varies by league convention; these new fields always identify the true home and away sides of the matchup.
  * **`tournament_name` reflects the specific competition where the data provider supplies one** — e.g., esports carries the league and season ("LEC Summer 2026"), ITF tennis carries the tournament, golf carries the tournament edition ("2026 The Open Championship"), and UFC carries the event name ("UFC 320"). Futures instruments without a home/away matchup (e.g., golf winner) carry `tournament_name` only.
  * **All newly created sports instruments carry the fields.** Instruments created before this change do not — treat them as optional keys when reading the metadata map.
</Update>

<Update label="July 13, 2026" description="v0.0.70" tags={["Breaking Change", "Institutional API"]} rss={{ title: "v0.0.70 - Changes to data retention starting with the Thursday, July 16 maintenance window", description: "During the maintenance window on Thursday, July 16, 2026, we will be pruning all executions. We will also prune market data up to 45 days out and orders 90 days out. Be sure to store everything you need before then. Trades and positions will be unaffected. If you require a backfill of old executions, we can provide a one-time-only backfill on request. Going forward, retention periods are: orders — 90 days, market data — 45 days, executions — 7 days." }}>
  * During the **Thursday, July 16, 2026 maintenance window**, we will prune all executions, market data beyond 45 days, and orders beyond 90 days.
  * **Trades and positions remain unchanged.**
  * Store what you need before the window.
    * **Backfill:** if you require old executions, we can provide a **one-time-only** backfill on request.
  * **Going-forward retention periods:**
    * orders — **90 days**
    * market data — **45 days**
    * executions — **7 days**
</Update>

<Update label="July 10, 2026" description="v0.0.69" tags={["Incentives", "Institutional API", "Retail API"]} rss={{ title: "v0.0.69 - Liquidity rewards reductions effective Monday, July 13 at midnight ET", description: "Liquidity rewards are reduced across several categories effective 12:00am ET, Monday July 13. WNBA $5k to $2k per game, MLB $20k to $12.5k per game (incl. all props), MLB futures $1k/day to $500/day, Motorsports $5k to $1k, UFC moneyline $15k to $10k and prelims $2.5k to $1k, PGA Tour $150k to $50k per tournament, MLS futures $1k/day to $500/day, ATP/WTA $2.5k to $1k per match, ITF $500 to $300 per match, and Esports $3k to $1.5k. Discount factors and target sizes are unchanged." }}>
  * **Liquidity rewards reductions, effective 12:00am ET, Monday July 13, 2026:**
    * **WNBA:** \$5,000 → **\$2,000** per game.
    * **MLB:** \$20,000 → **\$12,500** per game (incl. all props).
    * **MLB futures:** \$1,000/day → **\$500/day**.
    * **Motorsports:** \$5,000 → **\$1,000**.
    * **UFC:** Moneyline \$15,000 → **\$10,000**; prelims \$2,500 → **\$1,000**.
    * **PGA Tour:** \$150,000 → **\$50,000** per tournament.
    * **MLS futures:** \$1,000/day → **\$500/day**.
    * **ATP/WTA:** \$2,500 → **\$1,000** per match.
    * **ITF:** \$500 → **\$300** per match.
    * **Esports:** \$3,000 → **\$1,500**.
  * **Discount factors and target sizes unchanged.**
</Update>

<Update label="July 9, 2026" description="v0.0.68" tags={["Maintenance", "Institutional API", "Retail API"]} rss={{ title: "v0.0.68 - Weekly maintenance window moved to Thursday 2am-6am ET", description: "The recurring weekly maintenance window is now every Thursday from 2:00am-6:00am ET, effective July 9, 2026. Previously, the window was every Thursday, 6:00am-8:00am ET. This affects both the Institutional API and Retail API. View live status at https://status.polymarketexchange.com." }}>
  * **Weekly maintenance window moved to Thursday 2:00am–6:00am ET**, effective July 9, 2026. Previously, the window was every Thursday, 6:00am–8:00am ET. Affects both the Institutional API and Retail API.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="July 6, 2026" description="v0.0.67" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.67 - Scheduled maintenance window Tuesday, July 7, 2:00am-6:00am EDT", description: "FYI: a scheduled maintenance window is set for Tuesday, July 7 from 2:00am-6:00am EDT, affecting both the Institutional API and Retail API. Please note the time change as this is different than our normal hours. View live status at https://status.polymarketexchange.com." }}>
  * **Scheduled maintenance window — Tuesday, July 7, 2:00am–6:00am EDT.** Affects both the Institutional API and Retail API. Please note the time change, as this is different than our normal hours.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="July 5, 2026" description="v0.0.66" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.66 - Soccer To Advance is now a single two-sided moneyline instrument", description: "Soccer To Advance (soccer_game_to_advance) markets are now created as a single two-sided moneyline instrument carrying both teams, starting with the World Cup quarter-finals. The first is aadc-fwc-fra-mar-2026-07-09-to-advance (France vs Morocco, July 9) — one instrument, not the two separate per-team instruments used before. It has outcome_type moneyline and market_sport_type soccer_game_to_advance. All To Advance games from here on use this format." }}>
  * **Soccer To Advance is now a single two-sided instrument.** `soccer_game_to_advance` markets are created as **one moneyline instrument** carrying both teams (long and short), instead of two separate per-team Yes/No instruments. Live starting with the **World Cup quarter-finals**.
  * **First instrument:** `aadc-fwc-fra-mar-2026-07-09-to-advance` (France vs Morocco, July 9) — a single id. It is **not** two instruments (`aadc-fwc-fra-mar-2026-07-09-to-advance-fra` and `aadc-fwc-fra-mar-2026-07-09-to-advance-mar`).
  * **Fields:** `outcome_type` is `moneyline` and `market_sport_type` is `soccer_game_to_advance`.
  * **All To Advance games from here on use this format.** Read both sides off the one instrument — Retail: `marketSides` from `GET /v1/market/slug/{slug}`; Institutional: `long_participant_id` / `short_participant_id` from `SearchInstruments` / `GetInstrument`.
</Update>

<Update label="July 2, 2026" description="v0.0.65" tags={["Incentives", "Institutional API", "Retail API"]} rss={{ title: "v0.0.65 - Politics and tennis futures liquidity rewards reduced", description: "Politics and tennis winner futures liquidity rewards are reduced effective 8:00pm ET, Thursday July 2 (00:00 UTC, Friday July 3). Politics events earn $250/day, down from $500/day. ATP & WTA tournament winner futures earn $500/day per event, down from $1,000/day. Wimbledon winner futures earn $2,500 per draw per day — $5,000/day total across the men's and women's draws — down from $5,000 per draw ($10,000/day total). Discount factors and target sizes are unchanged." }}>
  * **Politics and tennis winner futures liquidity rewards are reduced, effective 8:00pm ET, Thursday July 2 (00:00 UTC, Friday July 3):**
    * **Politics**: \$500/day → **\$250/day** per event, pro-rated across all markets within the event.
    * **ATP & WTA winner futures**: \$1,000/day → **\$500/day** per tournament winner futures event.
    * **Wimbledon winner futures**: \$5,000 per draw per day → **\$2,500 per draw per day** (\$5,000/day total across the men's and women's draws, down from \$10,000/day).
  * **Discount factors and target sizes are unchanged.** Full details on the [live liquidity rewards page](https://polymarket.us/rewards).
</Update>

<Update label="July 2, 2026" description="v0.0.64" tags={["Upcoming", "Breaking Change", "Institutional API", "Retail API"]} rss={{ title: "v0.0.64 - Soccer To Advance, esports map/game winner, and tennis set winner become single two-sided instruments", description: "Heads up: Soccer To Advance (soccer_game_to_advance) markets become a SINGLE two-sided instrument carrying both participants (long and short) starting with the World Cup quarter-finals onward, instead of two separate per-team Yes/No instruments. Separately, esports map/game winner (esports_map_winner_1/2/3, esports_game_winner_1/2/3) and tennis set winner (tennis_set_1/2/3_winner) markets make the same change for newly created instruments starting Friday night (July 3, 2026). Existing instruments are unaffected in both cases." }}>
  * **Upcoming — these markets become a single two-sided instrument.** Instead of two separate per-team instruments, each of the following is created as **one instrument with both participants** (a single long/short winner market):
    * `soccer_game_to_advance` — Soccer To Advance, starting with the **World Cup quarter-finals onward**
    * `esports_map_winner_1` / `esports_map_winner_2` / `esports_map_winner_3` and `esports_game_winner_1` / `esports_game_winner_2` / `esports_game_winner_3` — esports map / game winner\*\*
    * `tennis_set_1_winner` / `tennis_set_2_winner` / `tennis_set_3_winner` — tennis set winner\*\*
  * **One market, two sides.** Each market now exposes a single instrument carrying both teams/players (`long_participant_id` / `short_participant_id`; Retail two-sided `marketSides`) rather than one Yes/No market per participant. Read both sides off the one instrument instead of expecting two separate markets per event.
  * **Effective for newly created instruments only.** Existing instruments keep their current shape. Soccer To Advance applies **starting with the World Cup quarter-finals onward**; esports map/game winner and tennis set winner apply to instruments created from **Friday night (July 3, 2026)** onward.
  * **Where to read it:** Retail — `marketSides` and `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `long_participant_id` / `short_participant_id` and `market_sport_type` from `SearchInstruments` / `GetInstrument`. See [Sports Schema](/trader-guide/sports-schema).
</Update>

<Update label="July 2, 2026" description="v0.0.63" tags={["New Feature", "Incentives", "Institutional API", "Retail API"]} rss={{ title: "v0.0.63 - Nathan's Hot Dog Eating Contest liquidity rewards ($13,000)", description: "The Nathan's Famous Hot Dog Eating Contest markets (July 4, 2026) now carry $13,000 in liquidity rewards, effective July 2. Men's contest: each of the four events (Chestnut to win, winner without Chestnut, winner's total hot dogs & buns, men's record broken) has $2,500 — $1,250 Early plus $1,250 Day-of ($10,000 total; discount factor 0.40/0.35, target size 2,500). Women's contest: each of the four events has $250 per day ($1,000/day total; discount factor 0.35, target size 2,500), distributed pro-rata across eligible instruments." }}>
  * **Nathan's Hot Dog Eating Contest markets (July 4, 2026) now carry \$13,000 in liquidity rewards**, effective July 2.
  * **Men's contest — \$10,000.** Each of the four men's events — Chestnut to win, winner without Chestnut, winner's total hot dogs & buns, and men's record broken — has **\$2,500**: \$1,250 Early + \$1,250 Day-of (discount factor 0.40/0.35, target size 2,500), distributed pro-rata across eligible instruments.
  * **Women's contest — \$1,000 per day.** Each of the four women's events — Sudo to win, winner without Sudo, winner's total hot dogs & buns, and women's record broken — has **\$250 per day** (discount factor 0.35, target size 2,500), distributed pro-rata across eligible instruments.
  * Full details on the [live liquidity rewards page](https://polymarket.us/rewards).
</Update>

<Update label="July 2, 2026" description="v0.0.62" tags={["Breaking Change", "Upcoming", "Retail API"]} rss={{ title: "v0.0.62 - lastPriceSample field no longer supported as of July 3", description: "The lastPriceSample field is being removed from both full and lite Retail Markets WebSocket market data responses, as well as the GET /v1/markets/{slug}/bbo and GET /v1/markets/{slug}/book REST endpoints. As of Friday, July 3, 2026, this field should no longer be considered supported. On the lite response and GET /v1/markets/{slug}/bbo, use longQuote/shortQuote instead." }}>
  * **`lastPriceSample` is being removed.** As of **Friday, July 3, 2026**, this field should no longer be considered supported — do not rely on it in your integration going forward.
  * **Where it appears:**
    * Retail Markets WebSocket (`wss://api.polymarket.us/v1/ws/markets`) — both `SUBSCRIPTION_TYPE_MARKET_DATA` and `SUBSCRIPTION_TYPE_MARKET_DATA_LITE` responses.
    * REST — `GET /v1/markets/{slug}/bbo` and `GET /v1/markets/{slug}/book`.
  * **Use `longQuote`/`shortQuote` instead** on the lite response (`SUBSCRIPTION_TYPE_MARKET_DATA_LITE` and `GET /v1/markets/{slug}/bbo`) — these fields already carry the equivalent data. The full response (`SUBSCRIPTION_TYPE_MARKET_DATA` and `GET /v1/markets/{slug}/book`) has no equivalent replacement field.
</Update>

<Update label="July 1, 2026" description="v0.0.61" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.61 - Scheduled maintenance window Thursday, July 2, 2:00am-6:00am EDT", description: "FYI: a scheduled maintenance window is set for Thursday, July 2 from 2:00am-6:00am EDT, affecting both the Institutional API and Retail API. Please note the time change as this is different than our normal hours. View live status at https://status.polymarketexchange.com." }}>
  * **Scheduled maintenance window — Thursday, July 2, 2:00am–6:00am EDT.** Affects both the Institutional API and Retail API. Please note the time change, as this is different than our normal hours.
  * **Live status:** [status.polymarketexchange.com](https://status.polymarketexchange.com).
</Update>

<Update label="June 29, 2026" description="v0.0.60" tags={["Bug Fix", "Institutional API", "Retail API"]} rss={{ title: "v0.0.60 - Wimbledon match winner markets are now decimalized (0.5c tick)", description: "Wimbledon and Wimbledon qualifiers match winner markets (tennis_match_winner) were initially listed with full cent ticks due to a bug. New markets for the rest of the tournament are now decimalized with a 0.5 cent ($0.005) tick size. Existing instruments are unaffected. Always read the tick size from the instrument before submitting orders — Retail market.orderPriceMinTickSize, Institutional instrument.tickSize." }}>
  * **Wimbledon match winner markets are now decimalized.** Wimbledon and Wimbledon qualifiers **match winner** markets (`tennis_match_winner`) were initially listed with full cent ticks. New markets for the rest of the tournament are decimalized with a **0.5 cent (`$0.005`)** tick size.
  * **Existing instruments are unaffected** — they keep the tick they were created with.
  * **Read the tick per instrument before trading.** Retail — `market.orderPriceMinTickSize` from `GET /v1/market/slug/{slug}`; Institutional — `instrument.tickSize` from `SearchInstruments` / `GetInstrument`. Do not assume 1 cent ticks.
</Update>

<Update label="June 28, 2026" description="v0.0.59" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.59 - Tennis sets spread and total sets markets are live", description: "Two new tennis market types are live: sets spread (tennis_match_sets_spread) and total sets (tennis_match_total_sets). Both are best-of aware (bo3 vs bo5) and settle on the official ATP/WTA result. Read sportsMarketType from the Retail market object or market_sport_type from Institutional instrument reference data." }}>
  * **Tennis props:**
  * **All tennis prop markets** (alongside the `tennis_match_winner` moneyline):
    * `tennis_match_games_spread` — handicap on games won
    * `tennis_match_sets_spread` — handicap on sets won
    * `tennis_match_total_games` — total games played across the match
    * `tennis_match_total_sets` — total sets played across the match
    * `tennis_match_exact_score` — exact set score
    * `tennis_set_1_winner` / `tennis_set_2_winner` / `tennis_set_3_winner` — per-set winner
</Update>

<Update label="June 27, 2026" description="v0.0.58" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.58 - Soccer first-half and second-half BTTS and First Team to Score markets", description: "Four new soccer market types are live: soccer_game_first_half_btts, soccer_game_first_half_first_team_to_score, soccer_game_second_half_btts, and soccer_game_second_half_first_team_to_score. Each settles on goals scored in its own half only — first-half markets count goals through minute 45 plus first-half stoppage time, second-half markets count minutes 46 through 90 plus second-half stoppage time, and extra-time goals never count. Read sportsMarketType from the Retail market object or market_sport_type from Institutional instrument reference data." }}>
  * **Soccer half BTTS and First Team to Score are live.** The following enums are added to `market_sport_type` (Retail `sportsMarketType`):
    * `soccer_game_first_half_btts` — both teams to score in the first half
    * `soccer_game_first_half_first_team_to_score` — first team to score in the first half (per-team plus a "None" outcome)
    * `soccer_game_second_half_btts` — both teams to score in the second half
    * `soccer_game_second_half_first_team_to_score` — first team to score in the second half (per-team plus a "None" outcome)
  * **Each market counts its own half only.** First-half markets count goals up to and including minute 45 (plus first-half stoppage time); second-half markets count minutes 46 through 90 (plus second-half stoppage time). Goals scored in extra time never count toward either half.
  * **Settlement timing.** First-half markets settle once the first half is complete (halftime); second-half markets settle at full time. If a half is goalless, the First Team to Score market resolves **None**.
  * **Standard 1 cent (`$0.01`) tick size** — these are not decimalized.
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`. See [Sports Schema](/trader-guide/sports-schema).
</Update>

<Update label="June 26, 2026" description="v0.0.57" tags={["Breaking Change", "Upcoming", "Retail API"]} rss={{ title: "v0.0.57 - Upcoming deprecations: Subjects endpoints and legacy market/event fields (migrate by June 29)", description: "Heads up: the Subjects API endpoints are deprecated, and several Market, MarketSide, and Event response fields are now deprecated in favor of structured replacements — sportsMarketType replaces marketType and sportsMarketTypeV2, marketSides replaces outcomes/outcomePrices, and event teams replaces participants. These deprecated endpoints and fields will be removed on June 29, 2026 — please migrate by then." }}>
  * **Subjects API is deprecated.** The Subjects endpoints — `GET /v1/subjects`, `GET /v1/subjects/{id}`, `GET /v1/subjects/slug/{slug}`, and their `/markets` variants — are deprecated and will be removed on **June 29, 2026**. They are no longer used, and their documentation has been removed from the API reference. If you currently depend on them, please reach out before the removal.
  * **Deprecated Market, MarketSide, and Event fields.** The following response fields are now marked deprecated in the API reference and will be removed on **June 29, 2026**. They continue to work until then — please migrate to the structured replacements:
    * Market `marketType` and `sportsMarketTypeV2` → `sportsMarketType`
    * Market `outcomes` / `outcomePrices` (JSON strings) → `marketSides[]`
    * Event `participants` → `teams`
    * `MarketSide.team` → the market side's participant data
    * `MarketSide.participantId`, and Market `archived`, `manualActivation`, `gameStartTime` → being removed from public responses
  * Deprecated fields are flagged in the [API reference](/api-reference/introduction) so you can identify them while migrating. Removal is scheduled for **June 29, 2026**.
</Update>

<Update label="June 27, 2026" description="v0.0.57" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.57 - Soccer extra-time markets live for World Cup knockouts", description: "Five new soccer extra-time market types are live on FIFA World Cup knockout fixtures: soccer_game_goes_to_extra_time, soccer_team_extra_time_spread, soccer_game_extra_time_total, soccer_game_extra_time_btts, and soccer_game_extra_time_first_team_to_score. All four scoring markets (spread, total, both teams to score, first team to score) settle on extra-time goals only — they exclude 90 minutes plus stoppage time and penalty shootouts. They are created pre-match for knockout games at the standard 1 cent ($0.01) tick size; if the match does not reach extra time these settle to the last fair market price. Read sportsMarketType from the Retail market object or market_sport_type from Institutional instrument reference data." }}>
  * **Soccer extra-time markets are live for the World Cup.** The following enums are added to `market_sport_type` (Retail `sportsMarketType`) on knockout fixtures:
    * `soccer_game_goes_to_extra_time` — binary Yes/No: will the match go to extra time?
    * `soccer_team_extra_time_spread` — spread on the extra-time goal margin
    * `soccer_game_extra_time_total` — Over/Under total goals in extra time
    * `soccer_game_extra_time_btts` — both teams to score in extra time
    * `soccer_game_extra_time_first_team_to_score` — first team to score in extra time (per-team plus a "None" outcome)
  * **Extra time only.** The spread, total, both-teams-to-score, and first-team-to-score markets count **only goals scored in extra time** — they exclude 90 minutes plus stoppage time and any penalty shootout. `soccer_game_goes_to_extra_time` settles **Yes** once the tie is level after regulation and proceeds to extra time.
  * **If the match does not reach extra time**, the four extra-time scoring markets settle to the **last fair market price** (`soccer_game_goes_to_extra_time` settles **No**).
  * **Created pre-match for knockout games**, alongside the other team props, once the main match market is open. Group-stage fixtures do not list these markets.
  * **Standard 1 cent (`$0.01`) tick size** — these extra-time markets are **not** decimalized. (Only the full-game World Cup spreads and totals use the 0.5 cent tick.)
  * **Example slugs** (Round of 32, South Africa vs Canada, `fwc-rsa-can-2026-06-28`):
    * Goes to extra time: `astatc-fwc-rsa-can-2026-06-28-goes-et`
    * Extra-time spread: `asc-fwc-rsa-can-2026-06-28-et-neg-1pt5` (and `-neg-0pt5`, `-pos-0pt5`, `-pos-1pt5`)
    * Extra-time total: `tsc-fwc-rsa-can-2026-06-28-et-1pt5`
    * Both teams to score (ET): `astatc-fwc-rsa-can-2026-06-28-et-btts`
    * First team to score (ET): `astatc-fwc-rsa-can-2026-06-28-et-ftts-rsa` (and `-can`, `-none`)
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`. See [Sports Schema](/trader-guide/sports-schema).
</Update>

<Update label="June 26, 2026" description="v0.0.56" tags={["New Feature", "Incentives", "Institutional API", "Retail API"]} rss={{ title: "v0.0.56 - Cricket expands to T20 leagues (MLC, T20 Blast M/W, Women's T20 World Cup, T20Is) with $500/match rewards", description: "Cricket coverage now spans international and domestic T20 in addition to IPL: T20 Internationals, Major League Cricket, the T20 Blast (men's and women's), and the Women's T20 World Cup. Each match lists a single match winner market (market_sport_type = cricket_match_winner) — the same structure as IPL — so no integration changes are needed. Every one of these matches carries $500 in liquidity rewards on the match winner market, split early/day-of/live $25/$75/$400 (discount factor 0.40/0.35/0.30, target size 10,000). IPL keeps its own $20,000 structure." }}>
  * **Cricket now covers international & domestic T20.** In addition to IPL, the match winner market is now live for **T20 Internationals**, **Major League Cricket**, the **T20 Blast (men's and women's)**, and the **Women's T20 World Cup**.
  * **Same market type — no integration changes.** Each match lists one match winner market (`market_sport_type = "cricket_match_winner"`, Retail `sportsMarketType = "cricket_match_winner"`), identical in structure to IPL. It resolves to the official match winner; a no result, tie, or abandonment with no declared winner resolves to **\$0.50**.
  * **Liquidity rewards — \$500 per match** on the match winner market, split **early / day-of / live = \$25 / \$75 / \$400** (discount factors 0.40 / 0.35 / 0.30, target size 10,000 each). IPL keeps its own \$20,000 structure.
  * **Example slugs** (Major League Cricket): `aec-mlc-sfu-soe-2026-06-27` (San Francisco Unicorns vs Seattle Orcas), `aec-mlc-mny-lakr-2026-06-27` (MI New York vs Los Angeles Knight Riders).
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`. See [Sports Schema](/trader-guide/sports-schema) and [Liquidity Rewards](https://polymarket.us/rewards).
</Update>

<Update label="June 26, 2026" description="v0.0.55" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.55 - Soccer To Advance market live for the World Cup (0.5c tick)", description: "The soccer To Advance market (market_sport_type soccer_game_to_advance) is now live for FIFA World Cup knockout fixtures. It is a binary Yes/No market per team that settles on the team that advances over the whole tie — regulation, extra time, and penalties. These markets are decimalized with a 0.5 cent ($0.005) tick size; read tick size from the instrument before submitting orders." }}>
  * **Soccer To Advance is live for the World Cup.** Knockout fixtures now list a To Advance market (`market_sport_type = soccer_game_to_advance`, Retail `sportsMarketType = "soccer_game_to_advance"`). It is created per knockout game once the main match market is open.
  * **Structure:** each knockout tie has **two separate instruments — one per team** (e.g. "Will South Africa advance?" and "Will Canada advance?"), each a binary Yes/No market. They resolve on the team that progresses over the **whole tie — regulation, extra time, and penalties** — not the 90-minute result.
  * **Decimalized 0.5 cent tick size (`$0.005`).** Do not assume 1 cent ticks. Read tick size per instrument before validating or submitting orders:
    * **Retail API:** `market.orderPriceMinTickSize` from `GET /v1/market/slug/{slug}` (expect `0.005`).
    * **Institutional API:** `instrument.tickSize` from `SearchInstruments` / `GetInstrument` (expect `0.005`); divide integer prices by `instrument.priceScale` (e.g. `priceScale == 1000` → `price = 5` is `$0.005`).
  * **Example slugs** (Round of 32, South Africa vs Canada, event `aadc-fwc-rsa-can-2026-06-28-to-advance`):
    * South Africa to advance: `aadc-fwc-rsa-can-2026-06-28-to-advance-rsa`
    * Canada to advance: `aadc-fwc-rsa-can-2026-06-28-to-advance-can`
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`. See [Sports Schema](/trader-guide/sports-schema).
</Update>

<Update label="June 25, 2026" description="v0.0.54" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.54 - One-off maintenance window Friday, June 26, 2:30am-4:30am EST", description: "FYI: a one-off maintenance window is scheduled for Friday, June 26 from 2:30am-4:30am EST, affecting both the Institutional API and Retail API. Please note the time change as this is different than our normal hours. View live status at https://status.polymarketexchange.com." }}>
  * **Maintenance window — Friday, June 26, 2:30am–4:30am EST.** Affects both the Institutional API and Retail API. Please note the time change, as this is different than our normal hours.
  * **Live status:** [status.polymarketexchange.com/incidents/d936p4wqsp77](https://status.polymarketexchange.com/incidents/d936p4wqsp77).
</Update>

<Update label="June 24, 2026" description="v0.0.53" tags={["Improvement", "Upcoming", "Retail API"]} rss={{ title: "v0.0.53 - Positions endpoint will be paginated (up to 100 per page) — follow nextCursor", description: "Coming soon: the Retail positions endpoint, GET /v1/portfolio/positions, will return results in pages of up to 100 positions instead of the full set in a single response. To retrieve all of your positions, follow the nextCursor value (sent as the cursor query parameter) until the response returns eof: true — accounts with more than 100 positions that do not paginate will only receive the first page. This change fixes timeouts and out-of-memory errors on very large position lists. We'll announce the enablement date here in advance." }}>
  * **`GET /v1/portfolio/positions` will be paginated.** The endpoint will return up to **100 positions per page** instead of the entire set in a single response.
  * **Action required for large accounts.** To retrieve all of your positions, follow the `nextCursor` value (sent as the `cursor` query parameter) until the response returns `eof: true`. Accounts with more than 100 positions that do not paginate will only receive the first page.
  * **No change for smaller accounts.** Accounts with 100 or fewer positions still receive every position in a single response, now with `eof: true`.
  * **Why:** returning every position in one response caused request timeouts and out-of-memory errors for accounts with very large position lists (tens of thousands of positions).
  * **Rollout:** rolling out soon — we'll announce the enablement date here in advance. Subscribe to the RSS feed to be notified before it ships.
  * **Where to read it:** `GET /v1/portfolio/positions`. See [Portfolio API](/api-reference/portfolio/overview).
</Update>

<Update label="June 23, 2026" description="v0.0.52" tags={["Improvement", "Institutional API", "Retail API"]} rss={{ title: "v0.0.52 - market_sport_type backfill complete; map on it alone, stop using outcome_type", description: "The backfill is complete: every open instrument in production now carries market_sport_type, including full-game winner/spread/total. You no longer need to check outcome_type to map a market — market_sport_type alone fully identifies structure and period. outcome_type is still present on the instrument but should not be relied on for mapping (it is subject to change). Futures are the only exception and remain identified by outcome_type = futures." }}>
  * **Backfill complete.** Every open instrument in production now carries `market_sport_type`, including full-game winner/spread/total and full-time/match/fight winner markets.
  * **Map on `market_sport_type` alone — you no longer need to check `outcome_type`.** `market_sport_type` fully identifies a market's structure and period on its own.
  * **`outcome_type` is still there, just don't rely on it for mapping.** It remains populated on every instrument but is subject to change; treat it as informational only and migrate any mapping logic to `market_sport_type`.
  * **One exception:** season/event-long **futures** carry no `market_sport_type` and are still identified by `outcome_type = "futures"`.
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`. See [Sports Schema](/trader-guide/sports-schema).
</Update>

<Update label="June 20, 2026" description="v0.0.51" tags={["New Feature", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.51 - market_sport_type on all instruments in production (Monday, June 22)", description: "Starting Monday, June 22, every instrument in production will have market_sport_type filled in — including full-game winner/spread/total — and we'll run a backfill of all open instruments. outcome_type remains on the instrument and is unchanged." }}>
  * **Starting Monday, June 22, 2026, every instrument in production will have `market_sport_type` filled in** — including full-game winner/spread/total (and full-time / match / fight winner), which previously left it unset (see v0.0.48 for the enum list).
  * **Backfill:** we'll backfill all open instruments with `market_sport_type` on Monday, June 22.
  * **`outcome_type` remains on the instrument** and is unchanged (`moneyline` / `spreads` / `totals` / `drawable_outcome`). However, please do not use this for mappings and use sport\_market\_type instead, outcome\_type will be deprecated in the coming weeks.
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`. See [Sports Schema](/trader-guide/sports-schema).
</Update>

<Update label="June 18, 2026" description="v0.0.50" tags={["Breaking Change", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.50 - market_sport_type on all instruments (prod Tuesday); outcome_type deprecated", description: "Tuesday, June 23: explicit market_sport_type rolls out to production on all instruments (including full-game winner/spread/total and full-time/match winner), and we backfill all open instruments at 12pm ET. You can fully identify an instrument from market_sport_type alone. outcome_type is deprecated and should NOT be relied on — it is subject to change." }}>
  * **Every instrument now carries an explicit `market_sport_type` — production Tuesday, June 23, 2026.** This adds full-game winner/spread/total and full-time/match winner markets, which previously left it unset (see v0.0.48 for the enum list).
  * **Backfill:** we'll backfill all open instruments with the new `market_sport_type` on **Tuesday, June 23 at 12:00pm ET**.
  * **You can now fully identify an instrument from `market_sport_type` alone** — it encodes both market structure (winner/spread/total) and period (full game, first half, etc.). Use it as your single source of truth going forward.
  * **`outcome_type` is deprecated.** Please don't rely on it — it's subject to change. Migrate any logic keyed off `outcome_type` to `market_sport_type` before Tuesday.
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`. See [Sports Schema](/trader-guide/sports-schema).
</Update>

<Update label="June 17, 2026" description="v0.0.49" tags={["Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.49 - Tennis match props", description: "New tennis match props are coming: games spread, total games, exact match score, and set winner. Read sportsMarketType from the Retail market object or market_sport_type from Institutional instrument reference data." }}>
  * **New tennis match props (coming soon).** The following enums are added to `market_sport_type` (Retail `sportsMarketType`):
    * **Games:** `tennis_match_games_spread`, `tennis_match_total_games`
    * **Match:** `tennis_match_exact_score`
    * **Set winner (one type per set):** `tennis_set_1_winner`, `tennis_set_2_winner`, `tennis_set_3_winner`
  * **Set Winner** covers only the guaranteed sets — best-of-3: sets 1-2 (`tennis_set_1_winner`, `tennis_set_2_winner`); best-of-5: sets 1-3 (adds `tennis_set_3_winner`).
  * **Exact Match Score** resolves on the final score in sets (best-of-3: `2-0` / `2-1`; best-of-5: `3-0` / `3-1` / `3-2`).
  * **Resolution:** games spread and total games settle on total games across the completed match; set winner settles per set; exact match score settles on the final sets score. If a match is not completed (walkover, retirement, cancellation, or postponement beyond the scheduled window), the market settles at the last fair market price.
  * **Coverage:** ATP and WTA singles matches.
  * **Example slugs** (ATP, event `atp-novdjo-caralc-2026-06-06`):
    * Games spread: `asc-atp-novdjo-caralc-2026-06-06-gs-neg-3pt5`
    * Total games: `tsc-atp-novdjo-caralc-2026-06-06-tg-22pt5`
    * Exact match score: `astatc-atp-novdjo-caralc-2026-06-06-es-2-0`
    * Set winner (Set 1): `astatc-atp-novdjo-caralc-2026-06-06-set1-sw1`
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`.
</Update>

<Update label="June 17, 2026" description="v0.0.48" tags={["New Feature", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.48 - Explicit market_sport_type on full-game/full-match markets (preprod)", description: "Newly created full-game winner/spread/total and full-match/full-time winner instruments now carry an explicit market_sport_type (e.g. basketball_team_full_game_spread, soccer_team_full_time_winner) — live in preprod now. outcome_type is unchanged, and instruments created before this change keep their current values (market_sport_type stays unset). New enums cover basketball, football, baseball, hockey, tennis, cricket, esports, UFC, and soccer." }}>
  * **Full-game and full-match markets now carry an explicit `market_sport_type` — live in preprod now.** Previously these markets left `market_sport_type` unset and were identifiable only by `outcome_type` (`moneyline`/`spreads`/`totals`/`drawable_outcome`). Newly created instruments now also carry a fine-grained `market_sport_type`, consistent with the existing period markets (e.g. `basketball_team_first_half_spread`). The following enums are added to `market_sport_type` (Retail `sportsMarketType`):
    * **Basketball — full game (NBA, WNBA, CBB, WCBB):** `basketball_team_full_game_winner`, `basketball_team_full_game_spread`, `basketball_team_full_game_total`
    * **Football — full game (NFL, CFB):** `football_team_full_game_winner`, `football_team_full_game_spread`, `football_team_full_game_total`
    * **Baseball — full game (MLB):** `baseball_team_full_game_winner`, `baseball_team_full_game_spread`, `baseball_team_full_game_total`
    * **Hockey — full game (NHL):** `hockey_team_full_game_winner`, `hockey_team_full_game_spread`, `hockey_team_full_game_total`
    * **Match / fight winner:** `tennis_match_winner`, `cricket_match_winner`, `esports_match_winner`, `ufc_fight_winner`
    * **Soccer — full-time 3-way winner:** `soccer_team_full_time_winner` (`outcome_type` stays `drawable_outcome`). Soccer full-game spread/total already carried `soccer_team_full_game_spread`/`soccer_team_full_game_total` and are unchanged.
  * **`outcome_type` is unchanged** and continues to be populated on new instruments (`moneyline`/`spreads`/`totals`/`drawable_outcome`), so existing structural logic keeps working.
  * **Existing instruments are not modified.** Instruments created before this change keep their current values and leave `market_sport_type` unset; the new enums appear only on newly created instruments. During the transition, treat a full-game market with an unset `market_sport_type` as full-game.
  * **Rollout:** live in **preprod** now. We'll announce the production date here in advance — subscribe to the RSS feed to be notified before it ships to production.
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`.
</Update>

<Update label="June 16, 2026" description="v0.0.47" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.47 - One-off maintenance window Wednesday, June 17, 6am-9am EST", description: "FYI: a maintenance window is scheduled for Wednesday, June 17 from 6:00am-9:00am EST, affecting both the Institutional API and Retail API. Please note the time change as this is different than our normal hours. This is a one-off time change." }}>
  * **Maintenance window — Wednesday, June 17, 6:00am–9:00am EST.** Affects both the Institutional API and Retail API. Please note the time change, as this is different than our normal hours. This is a one-off time change.
</Update>

<Update label="June 12, 2026" description="v0.0.46" tags={["Incentives", "Institutional API", "Retail API"]} rss={{ title: "v0.0.46 - World Cup futures liquidity rewards increased", description: "World Cup futures liquidity rewards increased (effective 12:00am ET, Friday June 12). Tournament Winner Futures raised from $1,500/day to $5,000/day, Group Winners & Golden Boot Futures from $750/day to $1,500/day, and Exotic Futures from $500/day to $1,000/day." }}>
  * **World Cup futures liquidity rewards increased (effective 12:00am ET, Friday June 12):**
    * **Tournament Winner Futures:** \$1,500/day → **\$5,000/day**.
    * **Group Winners & Golden Boot Futures:** \$750/day → **\$1,500/day**.
    * **Exotic Futures:** \$500/day → **\$1,000/day**.
  * **Discount factors and target sizes unchanged.**
</Update>

<Update label="June 11, 2026" description="v0.0.45" tags={["Improvement", "Institutional API", "Retail API"]} rss={{ title: "v0.0.45 - Soccer spread/total markets use spreads/totals outcome_type", description: "Soccer spread and total markets now carry outcome_type spreads/totals for every period, including first half, second half, and team totals (previously props). The period is still encoded by market_sport_type. Identify market structure from outcome_type and the period from market_sport_type." }}>
  * **Soccer spread/total markets now use the `spreads`/`totals` `outcome_type` for every period.** Previously, soccer first-half, second-half, and team-total markets were listed with `outcome_type = "props"`. They now use the same structural `outcome_type` as full-game spreads/totals, matching basketball and baseball period markets. The period is encoded by `market_sport_type`.
    * **Spread → `outcome_type = "spreads"`:** `soccer_team_first_half_spread`, `soccer_team_second_half_spread`.
    * **Total → `outcome_type = "totals"`:** `soccer_team_first_half_total`, `soccer_team_second_half_total`, `soccer_team_total_goals`, `soccer_team_total_goals_first_half`.
  * **Action recommended:** identify market structure from `outcome_type` and the period from `market_sport_type`. Do not assume soccer period spread/total markets are `props`. See [Sports Schema](/trader-guide/sports-schema).
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `outcome_type` and `market_sport_type` from `SearchInstruments` / `GetInstrument`.
</Update>

<Update label="June 11, 2026" description="v0.0.45" tags={["Incentives", "Institutional API", "Retail API"]} rss={{ title: "v0.0.45 - World Cup liquidity rewards increased to $50,000 per game", description: "World Cup liquidity rewards increased from $30,000 to $50,000 per game (effective 2:00pm ET, Thursday June 11). Moneyline/spreads/totals pool increased from $20,000 to $35,000, player props from $5,000 to $7,500, and team props from $5,000 to $7,500." }}>
  * **World Cup liquidity rewards increased (effective 2:00pm ET, Thursday June 11):** Total per game raised from \$30,000 → **\$50,000**.
    * **Moneyline/spreads/totals:** \$20,000 → **\$35,000** (Moneyline \$26,250, Spreads \$4,375, Totals \$4,375).
    * **Player Props:** \$5,000 → **\$7,500** (\$3,750 Pre-game + \$3,750 Live).
    * **Team Props:** \$5,000 → **\$7,500** (\$3,750 Pre-game + \$3,750 Live).
  * **Discount factors and target sizes unchanged.**
</Update>

<Update label="June 9, 2026" description="v0.0.44" tags={["Maintenance", "Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.44 - One-off maintenance window Thursday, June 11, 3am-5am EST", description: "FYI: a maintenance window is scheduled for Thursday, June 11 from 3:00am-5:00am EST. Please note the time change as this is different than our normal hours. This is a one-off time change." }}>
  * **Maintenance window — Thursday, June 11, 3:00am–5:00am EST.** Please note the time change, as this is different than our normal hours. This is a one-off time change.
</Update>

<Update label="June 9, 2026" description="v0.0.43" tags={["Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.43 - Full partial-contract rollout moved to June 11", description: "Amendment to the previous partial-contract rollout notice: we heard feedback that some users needed more time to fully migrate, so full rollout has moved to Thursday, June 11, 2026 at 5:00 PM ET (21:00 UTC). Long-dated futures listed before then and all World Cup instruments are partial-contract markets." }}>
  We heard feedback from some of our users that they needed more time to fully migrate to partial contracts, so we pushed back full rollout. All newly listed instruments will become partial-contract markets on **Thursday, June 11, 2026 at 5:00 PM ET (21:00 UTC)**. Long-dated futures markets listed before then and all World Cup instruments are partial-contract markets, so all market makers and API users should support partial-contract instruments now.
</Update>

<Update label="June 6, 2026" description="v0.0.42" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.42 - NHL hockey market types", description: "NHL hockey sports market types are live: game-to-overtime, game-to-double-overtime, and player goals, assists, and points. Read sportsMarketType from the Retail market object or market_sport_type from Institutional instrument reference data." }}>
  * **NHL hockey market types are live.** The following enums are added to `market_sport_type` (Retail `sportsMarketType`):
    * **Game:**
      * `hockey_game_overtime` (will the game go to overtime?)
      * `hockey_game_double_overtime` (will the game go to double overtime?)
    * **Player props:**
      * `hockey_player_goals`
      * `hockey_player_assists`
      * `hockey_player_points`
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`.
</Update>

<Update label="June 6, 2026" description="v0.0.41" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.41 - UFC market types", description: "UFC sports market types are live: method of victory, go the distance, round of victory, round of finish, and method of finish. Read sportsMarketType from the Retail market object or market_sport_type from Institutional instrument reference data." }}>
  * **UFC market types are live.** The following enums are added to `market_sport_type` (Retail `sportsMarketType`):
    * `ufc_method_of_victory`
    * `ufc_go_the_distance`
    * `ufc_round_of_victory`
    * `ufc_round_of_finish`
    * `ufc_method_of_finish`
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`.
</Update>

<Update label="June 6, 2026" description="v0.0.40" tags={["New Feature", "Institutional API", "Retail API"]} rss={{ title: "v0.0.40 - Soccer market types", description: "Soccer sports market types are live: full-game and first-half spread/total, full-time and first-half winner, both teams to score, first team to score, exact score, total corners, plus player goals and assists. Read sportsMarketType from the Retail market object or market_sport_type from Institutional instrument reference data." }}>
  * **Soccer market types are live.** The following enums are added to `market_sport_type` (Retail `sportsMarketType`):
    * **Team — full game:**
      * `soccer_team_full_time_winner`
      * `soccer_team_full_game_spread`
      * `soccer_team_full_game_total`
    * **Team — first half:**
      * `soccer_team_first_half_winner`
      * `soccer_team_first_half_spread`
      * `soccer_team_first_half_total`
    * **Game props:**
      * `soccer_game_btts` (both teams to score)
      * `soccer_game_first_team_to_score`
      * `soccer_game_exact_score`
      * `soccer_game_total_corners`
    * **Player props:**
      * `soccer_player_goals`
      * `soccer_player_assists`
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`.
</Update>

<Update label="June 5, 2026" description="v0.0.39" tags={["Incentives"]} rss={{ title: "v0.0.38 - NBA Playoffs props expansion + moneyline Live reduction + World Cup start", description: "NBA Playoffs props rewards expanded to $20,000/game across Player, Game, and Other props, and moneyline Live reduced from $56,500 to $50,000 per game (effective 1pm ET, Friday June 5). World Cup liquidity rewards start time updated to 6pm ET, Thursday June 4." }}>
  * **NBA Playoffs props expansion (effective 1:00pm ET, Friday June 5):** Props pool increased from \$10,000 → \$20,000 per game. Categories reorganized:
    * **Player Props:** \$10,000/game (\$5,000 Day-of + \$5,000 Live).
    * **Game Props (new):** \$5,000/game (\$2,500 Day-of + \$2,500 Live).
    * **Other Props (new):** \$5,000/game (\$2,500 Day-of + \$2,500 Live).
    * **Team Props removed.**
  * **NBA Playoffs Moneyline reduction (Live):** \$56,500 → **\$50,000** per game.
  * **NBA Playoffs total liquidity per game:** \$100,000 → **\$103,500** (\$83,500 moneyline/spreads/totals + \$20,000 props).
  * **NBA Pool row updated:** Early \$4,000 / Day-of \$14,000 / Live \$85,500.
  * **Props discount factor and target size** are consistent across all categories: **0.35 / 2,500** for both Day-of and Live.
  * **World Cup liquidity rewards:** start time pushed to **6:00pm ET, Thursday June 4** (was June 3).
</Update>

<Update label="June 4, 2026" description="v0.0.38" tags={["Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.38 - All new instruments are partial contracts starting June 8, 2026", description: "Starting Monday, June 8, 2026 at 12:00 PM EST, all newly listed instruments will be partial-contract markets. Do not assume whole-contract quantities. Derive the partial scale per instrument: Institutional reads instrument.fractionalQtyScale and instrument.minimumTradeQty; Retail reads minimumTradeQty from the market object and handles decimal quantity fields." }}>
  * **Starting Monday, June 8, 2026 at 12:00 PM EST, every newly listed instrument will be a partial-contract market.** Existing instruments are unchanged. Do not assume whole-contract quantities — derive the partial scale per instrument before submitting orders.
  * **Institutional API — derive the scale, then convert:**
    * `instrument.fractionalQtyScale` — divide raw integer quantities by this to get decimal contracts. For example, with `fractionalQtyScale == 100`, `quantity = 1` is `0.01` contracts and `quantity = 100` is `1` full contract.
    * `instrument.minimumTradeQty` — the smallest tradable integer quantity.
    * Initial partials use `fractionalQtyScale == 100` and `minimumTradeQty == 1`, so the minimum order is **1% of a contract**.
    * On the `Order` message, `fractional_quantity_scale` (field 49) carries the same scale for converting `order_qty`, `cum_qty`, and `leaves_qty`.
  * **Retail API — read the minimum, then handle decimals:**
    * `minimumTradeQty` on the market object (for example `GET /v1/market/slug/{slug}`) is expressed in contracts, so `0.01` means a **1%-of-a-contract** minimum.
    * Treat `quantity`, `cumQuantity`, and `leavesQuantity` as decimals, and use the decimal portfolio fields (`netPositionDecimal`, `qtyBoughtDecimal`, …).
</Update>

<Update label="June 2, 2026" description="v0.0.37" tags={["Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.37 - NBA quarter markets and game-to-overtime", description: "Basketball per-quarter (1st-4th) spread and total markets plus a game-to-overtime market are live in preprod now and deploy to production by midnight EST on June 2, 2026. The 4th-quarter markets exclude overtime. Read sportsMarketType from the Retail market object or market_sport_type from Institutional instrument reference data." }}>
  * **NBA quarter spread + total markets and game-to-overtime (preprod now, production by midnight EST on June 2, 2026).** The following enums are added to `market_sport_type` (Retail `sportsMarketType`):
    * **Spread:** `basketball_team_first_quarter_spread`, `basketball_team_second_quarter_spread`, `basketball_team_third_quarter_spread`, `basketball_team_fourth_quarter_spread`
    * **Total:** `basketball_team_first_quarter_total`, `basketball_team_second_quarter_total`, `basketball_team_third_quarter_total`, `basketball_team_fourth_quarter_total`
    * **Game-to-overtime:** `basketball_game_overtime`
  * **Resolution:** each quarter market settles on points scored in that quarter only; 4th-quarter markets exclude overtime. The game-to-overtime market settles at the conclusion of the game.
  * **Example slugs (NBA Finals, New York vs. San Antonio, `nba-ny-sa-2026-06-03`):**
    * 1st quarter spread: `asc-nba-ny-sa-2026-06-03-q1-neg-2pt5`, total: `tsc-nba-ny-sa-2026-06-03-q1-56pt5`
    * 4th quarter spread (excl. OT): `asc-nba-ny-sa-2026-06-03-q4-neg-1pt5`, total: `tsc-nba-ny-sa-2026-06-03-q4-51pt5`
    * Game-to-overtime: `astatc-nba-ny-sa-2026-06-03-ot`
  * **Where to read it:** Retail — `sportsMarketType` from `GET /v1/market/slug/{slug}`; Institutional — `market_sport_type` from `SearchInstruments` / `GetInstrument`.
</Update>

<Update label="June 1, 2026" description="v0.0.36" tags={["Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.36 - NBA second half team markets and new player props", description: "Basketball second-half spread, total, and moneyline team markets plus six new player props (rebounds, three-pointers made, steals, blocks, double-double, triple-double) are live in preprod now and deploy to production on June 2, 2026 at 6:00 PM EST. Read sportsMarketType from the Retail market object or market_sport_type from Institutional instrument reference data." }}>
  * **NBA second half + new player props (preprod now, production June 2, 2026 at 6:00 PM EST):** Basketball second-half team markets and six additional player props are live in preprod and will be deployed to production on **June 2, 2026 at 6:00 PM EST**. The following enums are added to the instrument `market_sport_type` field (Retail `sportsMarketType`):
    * **Team — second half:**
      * `basketball_team_second_half_winner`
      * `basketball_team_second_half_spread`
      * `basketball_team_second_half_total`
    * **Player props:**
      * `basketball_player_rebounds`
      * `basketball_player_threes`
      * `basketball_player_steals`
      * `basketball_player_blocks`
      * `basketball_player_double_double`
      * `basketball_player_triple_double`
  * **Example slugs (NBA Finals, New York vs. San Antonio, `nba-ny-sa-2026-06-03`):**
    * **Team — second half:**
      * 2H moneyline: `atc-nba-ny-sa-2026-06-03-sh-ny`, `atc-nba-ny-sa-2026-06-03-sh-sa`, `atc-nba-ny-sa-2026-06-03-sh-draw`
      * 2H spread: `asc-nba-ny-sa-2026-06-03-sh-neg-10pt5`, `asc-nba-ny-sa-2026-06-03-sh-pos-1pt5`
      * 2H total: `tsc-nba-ny-sa-2026-06-03-sh-105pt5`
    * **Player props** (each strike is its own market; player segment is first-3-of-first + first-3-of-last name):
      * Rebounds: `astatc-nba-ny-sa-2026-06-03-reb-vicwem-gte11`
      * Three-pointers made: `astatc-nba-ny-sa-2026-06-03-threes-jalbru-gte3`
      * Steals: `astatc-nba-ny-sa-2026-06-03-stl-jalbru-gte2`
      * Blocks: `astatc-nba-ny-sa-2026-06-03-blk-vicwem-gte2`
      * Double-double: `astatc-nba-ny-sa-2026-06-03-dd-vicwem-gte1`
      * Triple-double: `astatc-nba-ny-sa-2026-06-03-td-vicwem-gte1`
  * **Resolution — second half excludes overtime:** Second-half team markets (spread, total, moneyline) settle on points scored in the **third and fourth quarters only**; overtime is **not** included.
  * **Resolution — player props:** The new counting props (rebounds, three-pointers made, steals, blocks) settle on full-game box-score totals **including overtime**, consistent with the existing points and assists props. **Double-double** and **triple-double** resolve **Yes/No** — Yes when the player records 10 or more in at least two (double-double) or three (triple-double) of points, rebounds, assists, steals, or blocks.
  * **Where to read it:**
    * **Retail API** — read `sportsMarketType` from the market object (for example `GET /v1/market/slug/{slug}`).
    * **Institutional API** — read `market_sport_type` from instrument reference data (`SearchInstruments` / `GetInstrument`).
</Update>

<Update label="May 31, 2026" description="v0.0.35" tags={["Upcoming", "Retail API", "Institutional API"]} rss={{ title: "v0.0.35 - NBA Finals 0.5c tick sizes", description: "New York vs. San Antonio Game 2 of the NBA Finals, slug aec-nba-ny-sa-2026-06-05, will be listed on Monday, June 1, 2026 and will be the first market with a 0.5 cent tick size. The remainder of NBA Finals markets will also use 0.5 cent ticks. Clients should read tick size from the Retail market object or Institutional instrument reference data before submitting orders." }}>
  * **NBA Finals Game 2:** New York vs. San Antonio Game 2 of the NBA Finals (`aec-nba-ny-sa-2026-06-05`) will be listed on **Monday, June 1, 2026** and will be the first market with a **0.5 cent** tick size (`$0.005`). The remainder of NBA Finals markets will also use **0.5 cent** ticks.
  * **Retail API:** read `market.orderPriceMinTickSize` from the market response before submitting orders. For this market, use `GET /v1/market/slug/aec-nba-ny-sa-2026-06-05` and expect `orderPriceMinTickSize: 0.005`.
  * **Institutional API:** read `instrument.tickSize` from instrument reference data (`SearchInstruments` / `GetInstrument`). For this instrument, `instrument.tickSize = 0.005`.
  * **Institutional price scale:** prices submitted to the Institutional API are integer values. Read `instrument.priceScale` from the same instrument reference data response and divide submitted or returned integer prices by that value to get dollar prices. For example, if `instrument.priceScale == 1000`, `price = 5` means `$0.005`, `price = 500` means `$0.50`, and `price = 1000` means `$1.00`. With a 0.5 cent tick and `priceScale == 1000`, valid integer prices move in 5-unit increments.
  * **Action recommended:** do not assume 1 cent ticks. Read tick size and price scale per market or instrument before validating or submitting orders.
</Update>

<Update label="May 30, 2026" description="v0.0.34" tags={["New Feature", "Retail API"]} rss={{ title: "v0.0.34 - Retail API partial contracts and decimalized tick sizes", description: "Retail API schemas now document decimal order quantities, per-market minimumTradeQty, per-market orderPriceMinTickSize, decimal portfolio quantity fields, and legacy field deprecations for partial-contract markets." }}>
  * **Markets API:** market responses now document `minimumTradeQty` alongside `orderPriceMinTickSize`.
    * Applies to `GET /v1/markets`, `GET /v1/market/id/{id}`, `GET /v1/market/slug/{slug}`, and documented Retail API responses that embed the market object, including Events, Search, Sports, Sports Legacy, and Subjects.
    * `minimumTradeQty` is expressed in contracts. For example, `0.01` means the minimum order size is 1% of a contract.
    * `orderPriceMinTickSize` is expressed in dollars. For example, `0.005` means half-cent ticks.
  * **Market data:** order book and trade quantity fields can contain decimal contract quantities.
    * `GET /v1/markets/{slug}/book` and Markets WebSocket book levels return `qty` as a decimal string.
    * Markets WebSocket trade `quantity.value` is also a decimal string.
  * **Orders API:** order `quantity` fields support decimal contract quantities on partial-contract markets.
    * Applies to `POST /v1/orders`, `POST /v1/order/preview`, `POST /v1/order/{orderId}/modify`, `POST /v1/orders/batched`, and `POST /v1/orders/batched/modify`.
    * Order request and response `quantity`, `cumQuantity`, and `leavesQuantity` fields are JSON numbers and can contain decimals.
    * Private WebSocket order snapshots and updates use the same order quantity fields; execution `lastShares` is a decimal string.
    * Multi-leg execution `legPrices[].qty` is a decimal string.
    * Submit prices and quantities already aligned to the market's documented precision. Extra precision can be normalized in responses rather than rejected.
  * **Portfolio API:** use decimal quantity fields for positions and trades.
    * `GET /v1/portfolio/positions` returns `netPositionDecimal`, `qtyBoughtDecimal`, `qtySoldDecimal`, `bodPositionDecimal`, and `qtyAvailableDecimal`.
    * `GET /v1/portfolio/activities` trade payloads return `qtyDecimal`; the older trade `qty` field is rounded and deprecated.
    * Private WebSocket position messages can include `netPositionDecimal`, `qtyBoughtDecimal`, `qtySoldDecimal`, `bodPositionDecimal`, and `qtyAvailableDecimal`.
    * The older integer position fields `netPosition`, `qtyBought`, `qtySold`, `bodPosition`, and `qtyAvailable` remain for backward compatibility but are rounded and deprecated for partial-contract markets. `availablePositions` is also deprecated.
  * **Action recommended:** regenerate clients from the updated OpenAPI schemas and read quantity/tick constraints from each market before submitting orders. Do not assume whole-contract quantities or 1-cent price ticks, and do not rely on server-side rejection for extra decimal precision.
</Update>

<Update label="May 29, 2026" description="v0.0.34" tags={["New Feature", "Institutional API"]} rss={{ title: "v0.0.34 - Order fractional quantity scale and price-to-quantity-filled fields", description: "The Order message gains two additive fields: fractional_quantity_scale (field 49) for converting raw integer quantities to decimal, and price_to_quantity_filled (field 41), a map of price to quantity filled over the life of the order. They appear on every Institutional Trading and Report response that returns an Order or Execution, including the gRPC order stream." }}>
  * **Two additive fields on the `Order` message:**
    * `fractional_quantity_scale` (field 49, `int64`) — the fractional quantity scale copied from the instrument at order creation time. Divide raw integer quantities (`order_qty`, `cum_qty`, `leaves_qty`, etc.) by this value to get the properly scaled decimal quantity.
    * `price_to_quantity_filled` (field 41, `map<int64, int64>`) — quantity filled at each price point over the life of the order. The key is the price, the value is the quantity filled at that price.
  * **Where they appear:** every response that returns an `Order` or an `Execution` (which embeds `Order`), across the Institutional Trading and Report APIs and the gRPC order stream:
    * Trading API: `GET /v1/trading/orders/open` (`GetOpenOrders`) and the `CreateOrderSubscription` stream (snapshot orders and `update.executions[].order`).
    * Report API: `POST /v1/report/orders/search` (`SearchOrders`), `GET /v1/report/orders/{order_id}` (`GetOrder`), `POST /v1/report/executions/search` (`SearchExecutions`), and `GET /v1/report/executions/{exec_id}` (`GetExecution`).
  * **Backward compatible:** both fields are additive. Existing clients are unaffected; unset values decode as the proto defaults (`0` and an empty map).
  * **Action recommended:** rebuild your gRPC clients from the latest proto bundle to pick up the new fields.
</Update>

<Update label="May 28, 2026" description="v0.0.33" tags={["Upcoming", "Institutional API"]} rss={{ title: "v0.0.33 - Preprod partial contracts and decimalized tick sizes", description: "Dummy instruments are open in preprod for partial contract quantity handling plus 0.5c and 0.25c tick-size testing. Clients should read the instrument fields directly for quantity and price scaling." }}>
  * **Partial contracts in preprod:** `aec-mlb-az-mil-2026-06-15` is open in preprod as a dummy partial contract instrument.
    * Read `instrument.fractionalQtyScale` to determine how submitted integer order quantities are scaled. For example, if `instrument.fractionalQtyScale == 100`, submitting `quantity = 1` means 0.01 contracts, `quantity = 50` means 0.50 contracts, and `quantity = 100` means 1 full contract.
    * Read `instrument.minimumTradeQty` for the lowest scaled integer quantity that can be traded. For example, if `instrument.minimumTradeQty == 1` and `instrument.fractionalQtyScale == 100`, the minimum valid order quantity is `1`, which represents 0.01 contracts, or 1% of a contract.
    * Initial partial contract instruments will have `instrument.fractionalQtyScale == 100` and `instrument.minimumTradeQty == 1`, meaning the minimum order size is **1% of a contract**.
  * **Decimalization in preprod:** dummy instruments are open in preprod for smaller tick-size handling:
    * `aec-nba-mil-was-2026-06-15` has a **0.5c** tick size.
    * `aec-nhl-edm-ana-2026-06-15` has a **0.25c** tick size.
    * Read `instrument.priceScale` to determine how submitted integer order prices are scaled. For example, if `instrument.priceScale == 1000`, submitting `price = 5` means \$0.005, `price = 500` means \$0.50, and `price = 1000` means \$1.00.
    * Read `instrument.tickSize` for the tick size in dollars. For example, a 0.5c tick size is expressed as `instrument.tickSize = 0.005`, and a 0.25c tick size is expressed as `instrument.tickSize = 0.0025`.
  * **Action recommended:** read these values from the instrument before submitting orders. Do not infer quantity scale, price scale, or tick size from symbol, product category, or market type.
</Update>

<Update label="May 26, 2026" description="v0.0.32" tags={["New Feature", "Institutional API"]} rss={{ title: "v0.0.32 - Ledger endpoints, InstrumentStats fields, KeepAliveCommand", description: "New position and balance ledger endpoints (REST + gRPC stream), new InstrumentStats fields (last_trade_qty, settlement_set_time), and a new KeepAliveCommand on BiDirectionalStreamMarketData." }}>
  * **New ledger endpoints** for reconciliation, point-in-time replay, and end-of-day reporting:
    * **Position ledger (REST):** `GET /v1/positions/ledger`, `GET /v1/positions/ledger/download` — paginated query + streamed CSV of position changes (with both deltas and post-change cumulative state). See [Position Ledger](/institutional/positions/overview#position-ledger).
    * **Balance ledger (REST):** `GET /v1/funding/balance-ledger`, `GET /v1/funding/balance-ledger/download` — paginated query + streamed CSV of cash balance changes (deposits, withdrawals, fills, fees, corrections). See [Balance Ledger](/institutional/funding/overview).
    * **Balance ledger (gRPC):** `CreateBalanceLedgerSubscription` for real-time push of balance ledger entries. See [Balance Ledger Stream](/streaming-endpoints/balance-ledger-stream).
    * All three are scoped under `read:positions`. Both ledgers enforce a hard historical floor of **`2026-05-01T00:00:00Z`**; pre-floor entries are not retrievable.
  * **`InstrumentStats` additions** on the market data stream and `GetOrderBook` / `GetBBO` responses:
    * `last_trade_qty` (field 14, `optional int64`) — quantity of the most recent trade. Populated after any trade executes on the instrument.
    * `settlement_set_time` (field 15, `optional google.protobuf.Timestamp`) — timestamp when the settlement price was set. Populated only when the instrument is in a settled state.
  * **New `KeepAliveCommand`** on `BiDirectionalStreamMarketDataRequest` (field `keepalive = 7`). Sending one puts a client-to-server frame on the wire without modifying subscription state; the server returns no response. Solves the AWS Application Load Balancer 1-hour idle timeout (`RST_STREAM`) for long-lived bidirectional subscriptions with no client-to-server traffic. Recommended cadence: every **30–60 minutes** (well below the 3600s ALB timeout). Only applies to `BiDirectionalStreamMarketData`; server-streaming `CreateMarketDataSubscription` is not affected.
  * **Stream limits relaxed:** the per-firm cap is now **20 concurrent streams** with no per-stream-type restrictions. Previously, some stream types had individual caps; now the 20-stream budget is pooled across all gRPC subscriptions.
  * **Action recommended:** rebuild your gRPC clients from the latest proto bundle to pick up the new endpoints and additive fields above.
</Update>

<Update label="May 26, 2026" description="v0.0.32" tags={["New Feature", "Retail API"]} rss={{ title: "v0.0.32 - Portfolio activity types for taker fee rebates and liquidity program", description: "GET /v1/portfolio/activities now returns ACTIVITY_TYPE_TAKER_FEE_REBATE and ACTIVITY_TYPE_LIQUIDITY_PROGRAM for taker rebate credits and liquidity program payouts respectively. Both previously surfaced under ACTIVITY_TYPE_REFERRAL_BONUS / ACTIVITY_TYPE_TRANSFER." }}>
  * **Portfolio Activities API:** added two activity types now returned by `GET /v1/portfolio/activities`:
    * `ACTIVITY_TYPE_TAKER_FEE_REBATE` — taker fee rebate credit. Previously surfaced under `ACTIVITY_TYPE_REFERRAL_BONUS`.
    * `ACTIVITY_TYPE_LIQUIDITY_PROGRAM` — liquidity program payout. Previously surfaced under `ACTIVITY_TYPE_TRANSFER`.
  * Both carry an `accountBalanceChange` payload identical in shape to other balance-change activities.
  * Clients that have not regenerated against the updated OpenAPI schema will decode the new values as unknown enum members. Regenerate to surface the proper label.
</Update>

<Update label="May 21, 2026" description="v0.0.31" tags={["Incentives"]} rss={{ title: "v0.0.31 - Incentive reward updates", description: "Volume incentives are now live with NBA Playoffs Moneyline rewards, while select liquidity rewards were reduced for MLB Futures, IPL Games, and Politics events." }}>
  * **Volume Incentive Program is now live:** Program status moved from coming soon to open, with rewards based on share of eligible **taker-side notional** volume.
  * **Increase / new reward launch:** Added **NBA Playoffs Moneyline Volume Rewards** with a **\$100,000 in-game reward pool per market** (live May 21, 2026).
  * **Volume eligibility details:** only trades executed between **\$0.03 and \$0.97** count; minimum **\$500 notional** required to qualify for payout.
  * **Reduction — MLB Futures:** reduced from **\$5,000/day** (pooled across instruments) to **\$1,000/day**.
  * **Reduction — IPL Games:** reduced from **\$40,000/game** to **\$20,000/game**; moneyline split updated to **\$500 / \$1,500 / \$18,000** (Early / Day-of / Live).
  * **Reduction — Politics events:** reduced from **\$5,000/day** to **\$1,000/day**.
</Update>

<Update label="May 21, 2026" description="v0.0.30" tags={["Upcoming", "Institutional API", "Retail API"]} rss={{ title: "v0.0.30 - NBA Props live in production; derive tick size per instrument", description: "Basketball player props and first half markets go live in production the morning of May 22, 2026. Reminder: always derive tick size from the instrument — do not assume all instruments under a single contract type share the same tick. Upcoming World Cup futures are TEC contracts but will not be decimalized." }}>
  * **NBA Props (production):** Basketball player props and first half markets are going live in production the morning of **May 22, 2026**. The `market_sport_type` enums previously released to preprod will be active in production:
    * `basketball_player_points`
    * `basketball_player_assists`
    * `basketball_team_first_half_winner`
    * `basketball_team_first_half_spread`
    * `basketball_team_first_half_total`
  * **Tick size — always read from the instrument, not the contract type:** Do not assume that every instrument under a given contract type shares the same minimum price increment. Notably, **upcoming World Cup futures are Title Event Contracts (TEC) but will not be decimalized**, so they will not share a tick size with existing TEC futures. Pull the tick from the instrument before submitting any order.
    * **Retail API** — read `market.orderPriceMinTickSize` from `GET /v1/market/slug/{slug}`.
    * **Institutional API** — read `instrument.tickSize` from the instrument reference data response (`SearchInstruments` / `GetInstrument`).
</Update>

<Update
  label="May 21, 2026"
  description="v0.0.28"
  tags={["Upcoming","Retail API"]}
  rss={{
title: "v0.0.28 - Removing usernames from trade tape",
description: "Usernames are being removed from the Retail API trade tape responses for privacy.",
}}
>
  * **Retail API:** Removing usernames from trade tape responses
</Update>

<Update label="May 20, 2026" description="v0.0.29" tags={["Upcoming", "Institutional API"]} rss={{ title: "v0.0.29 - NBA Props enums in preprod", description: "Added basketball player props and first half market enums to the instrument market_sport_type field. Available in preprod." }}>
  * **NBA Props (preprod):** Added the following enums to the instrument `market_sport_type` field:
    * `basketball_player_points`
    * `basketball_player_assists`
    * `basketball_team_first_half_winner`
    * `basketball_team_first_half_spread`
    * `basketball_team_first_half_total`
</Update>

<Update label="May 4, 2026" description="v0.0.27" tags={["Bug Fix", "Institutional API"]} rss={{ title: "v0.0.27 - Execution response fields", description: "Commission and trade date fields now exposed on all execution-level responses including SearchExecutions, DownloadExecutions, and CreateOrderSubscription." }}>
  * **Execution responses:** Now exposing commission and trade date fields on all execution-level responses:
    * `commissionNotionalCollected` - Commission amount collected
    * `commissionSpreadPx` - Commission spread price
    * `transactTradeDate` - Trade transaction date
  * Applies to: SearchExecutions, DownloadExecutions, and CreateOrderSubscription execution updates
</Update>

<Update label="April 21, 2026" description="v0.0.26" tags={["New Feature", "Retail API"]} rss={{ title: "v0.0.26 - Retail batch endpoints and schema updates", description: "Documented batched order endpoints and added outcomeSide/action as alternative to intent on CreateOrderRequest. New enum members added to schema." }}>
  * **Retail Orders API:** documented three batched endpoints: `POST /v1/orders/batched`, `/v1/orders/batched/cancel`, `/v1/orders/batched/modify`. The first two were already shipped; the third is new.
  * **Retail Orders API:** documented `outcomeSide` + `action` as an alternative to `intent` on `CreateOrderRequest`, and added both fields to the `Order` response. `intent` is no longer marked `required` on `CreateOrderRequest`. Existing requests that send `intent` keep working; regenerated clients will see it flip from required to optional.
  * **Retail Orders API:** added enum members that were already on the wire but missing from the schema: `TIME_IN_FORCE_DAY`, `ORDER_STATE_NEW`, `EXECUTION_TYPE_NEW`, `ORD_REJECT_REASON_EXCHANGE_OPTION`.
</Update>

<Update label="April 17, 2026" description="v0.0.25" tags={["Documentation", "Institutional API"]} rss={{ title: "v0.0.25 - gRPC endpoint correction", description: "Corrected production gRPC endpoint from grpc-api.polymarketexchange.com to grpc-api.prod.polymarketexchange.com." }}>
  * Corrected production gRPC endpoint from `grpc-api.polymarketexchange.com` to `grpc-api.prod.polymarketexchange.com`
</Update>

<Update label="April 13, 2026" description="v0.0.24" tags={["Maintenance"]} rss={{ title: "v0.0.24 - Maintenance window change", description: "Weekly maintenance window moved from Tuesday 4am-6am ET to Thursday 6am-8am ET, effective April 16, 2026." }}>
  * Weekly maintenance window moved from **Tuesday 4am–6am ET** to **Thursday 6am–8am ET**, effective April 16, 2026
</Update>

<Update label="April 10, 2026" description="v0.0.23" tags={["Breaking Change", "Institutional API", "Retail API"]} rss={{ title: "v0.0.23 - Rate limit updates", description: "Rate limits reduced across all APIs: Institutional Gateway to 100 msg/s, FIX to 150 msg/s, Retail API to 20 req/s." }}>
  * Updated rate limits across all APIs:
    * Institutional Gateway (REST/gRPC): reduced to **100 messages per second** per firm
    * FIX Protocol: reduced to **150 messages per second** per session (all participants)
    * Retail API: reduced to **20 requests per second** per API key
</Update>

<Update label="March 30, 2026" description="v0.0.22" tags={["Breaking Change", "Bug Fix", "Documentation", "Institutional API"]} rss={{ title: "v0.0.22 - FIX field and route corrections", description: "FIX Product field now optional. Corrected REST API routes and production base URLs across documentation." }}>
  * FIX API: `Product` field (tag 460) changed from required to optional on New Order Single. All current products on Polymarket are `Product=12` (OTHER).
  * Corrected REST API routes: `/v1/accounts/whoami` → `/v1/whoami`, `/v1/accounts/users` → `/v1/users`, `/v1/accounts/accounts` → `/v1/accounts`
  * Fixed price scale examples across documentation to reflect correct values
  * Corrected production API base URLs to `api.prod.polymarketexchange.com` across all documentation
</Update>

<Update label="March 3, 2026" description="v0.0.21" tags={["Improvement", "Institutional API"]} rss={{ title: "v0.0.21 - Proto state field now optional", description: "State field changed from required to optional in MarketDataUpdate, GetOrderBookResponse, and GetBBOResponse. Use instrument state subscription for state changes." }}>
  * Edited proto files to improve the gRPC streaming experience
  * `state` field changed from required to optional in three messages:
    * `MarketDataUpdate.state` (field 4) in `marketdatasubscription.proto`
    * `GetOrderBookResponse.state` (field 4) in `orderbook.proto`
    * `GetBBOResponse.state` (field 6) in `orderbook.proto`
  * Participants should utilize the instrument state change subscription for state changes
</Update>

<Update label="February 26, 2026" description="v0.0.20" tags={["Improvement", "Institutional API"]} rss={{ title: "v0.0.20 - Settlement and price_scale fields", description: "Added settlement_price_calculation_text to settlement responses and price_scale to order messages." }}>
  * Updated settlement responses in `marketdatasubscription`, adding `settlement_price_calculation_text`
  * Added `price_scale` to order message
</Update>

<Update label="January 10, 2026" description="v0.0.19" tags={["New Feature", "Institutional API"]} rss={{ title: "v0.0.19 - Bidirectional market data streaming", description: "New BiDirectionalStreamMarketData RPC allows dynamic symbol subscription without reconnecting. Includes new Go and Python examples." }}>
  * Added Bidirectional Market Data Streaming API: `BiDirectionalStreamMarketData` RPC
  * Dynamically add and remove symbols during subscription lifetime without reconnecting
  * New response types: `SubscriptionAck` and `SubscriptionError` for subscription management
  * Updated client sample code with new Go and Python examples (Example 20)
  * Updated proto packages with bidirectional streaming support
</Update>

<Update label="January 4, 2026" description="v0.0.18" tags={["New Feature", "Institutional API"]} rss={{ title: "v0.0.18 - Account Valuation APIs", description: "New valuation endpoints for book-close accounting with historical queries via as_of_time or as_of_date. Includes CSV download for multi-account summaries." }}>
  * Added Account Valuation APIs for book-close accounting use cases
  * `POST /v1/valuations/accounts/statement/download`: Multi-account summaries as CSV
  * All new endpoints support historical queries via `as_of_time` or `as_of_date`
  * Cross-ISV protection enforced on all valuation endpoints
</Update>

<Update label="January 3, 2026" description="v0.0.17" tags={["New Feature", "Institutional API"]} rss={{ title: "v0.0.17 - Instrument query filters", description: "Added configurable instrument queries with pagination, state filtering, and sports league metadata filters." }}>
  * Documented configurable instrument queries: pagination, state filtering, and metadata filters
  * Added sports league filtering via `metadata.sports_game_league` (nfl, nba, mlb, nhl, cbb, cfb)
  * Added instrument metadata field documentation with sports-specific attributes
</Update>

<Update label="January 3, 2026" description="v0.0.16" tags={["New Feature", "Institutional API"]} rss={{ title: "v0.0.16 - Historical Positions API", description: "Query positions at any point in time using as_of_time or as_of_date for end-of-day reporting and regulatory snapshots." }}>
  * Added Historical Positions API: query positions at any point in time using `as_of_time` (RFC3339 timestamp) or `as_of_date` (trade date)
  * Use cases: end-of-day reporting, regulatory snapshots, position reconciliation
</Update>

<Update label="January 3, 2026" description="v0.0.15" tags={["Documentation"]} rss={{ title: "v0.0.15 - Documentation refresh", description: "Documentation deployment refresh with no API changes." }}>
  * Documentation deployment refresh
</Update>

<Update label="December 31, 2025" description="v0.0.14" tags={["Improvement", "Institutional API"]} rss={{ title: "v0.0.14 - Slow consumer handling and proto downloads", description: "Added skip-to-head behavior for slow consumers on streaming endpoints. Proto files now available for direct download." }}>
  * Added slow consumer handling option for streaming endpoints with skip-to-head behavior
  * Proto files now available for direct download (polymarket-protos.zip)
  * Added FAQ clarifying ISV-Participant relationship and participant\_id usage
</Update>

<Update label="December 8, 2025" description="v0.0.13" tags={["New Feature", "Institutional API"]} rss={{ title: "v0.0.13 - 25 REST API endpoints", description: "Added 25 REST API endpoints with full OpenAPI documentation covering Authentication, Accounts, Orders, Positions, Market Data, and Drop Copy." }}>
  * Added 25 REST API endpoints with full OpenAPI documentation
  * New sections: Authentication, Accounts, Orders, Positions, Market Data, Drop Copy
  * Organized API documentation by functional category
</Update>

<Update label="November 25, 2025" description="v0.0.12" tags={["Documentation", "Institutional API"]} rss={{ title: "v0.0.12 - gRPC and proto documentation", description: "Complete gRPC streaming documentation with Python examples, Protocol Buffer reference, VPC setup guide, and troubleshooting guide." }}>
  * Added complete gRPC streaming API documentation with Python code examples for market data and order execution streams
  * Introduced Protocol Buffer reference documentation with detailed message structures and field definitions
  * Added VPC connection setup guide with AWS PrivateLink configuration instructions
  * Created common pitfalls troubleshooting guide for integration issues
</Update>

<Update label="August 18, 2025" description="v0.0.11" tags={["Documentation", "Institutional API"]} rss={{ title: "v0.0.11 - Aesthetic updates", description: "Documentation aesthetic improvements including new figures and cleaner FIX example formatting." }}>
  * Aesthetic changes including new figures and cleaner formatting of FIX examples.
</Update>

<Update label="August 14, 2025" description="v0.0.10" tags={["Documentation"]} rss={{ title: "v0.0.10 - Initial documentation", description: "First draft of Polymarket Exchange Documentation." }}>
  * First DRAFT of Polymarket Exchange Documentation
</Update>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.