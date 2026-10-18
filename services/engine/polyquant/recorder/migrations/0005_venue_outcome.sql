-- Venue-declared result (from outcomePrices once RESOLVED). Used for settlement and research labels.
ALTER TABLE instruments ADD COLUMN venue_outcome text CHECK (venue_outcome IN ('UP', 'DOWN'));
