# Strategy 02 v1.4 — Full-body Jaw break

V1.4 keeps V1.3's completed **1-hour** ZigZag support/resistance and Alligator
context, with **15-minute** execution. It corrects the entry rule identified
during visual review.

## Valid long trigger

- The previous 15-minute Heikin-Ashi close was at or below its Jaw.
- The completed trigger candle's Heikin-Ashi **open and close are both above**
  its 15-minute Jaw.
- The next immediate 15-minute bar is the entry reference.

## Valid short trigger

- The previous 15-minute Heikin-Ashi close was at or above its Jaw.
- The completed trigger candle's Heikin-Ashi **open and close are both below**
  its 15-minute Jaw.
- The next immediate 15-minute bar is the entry reference.

A candle that merely closes across the Jaw while its body still straddles the
Jaw is rejected. Wicks may cross the Jaw; the full-body condition concerns the
Heikin-Ashi open and close.
