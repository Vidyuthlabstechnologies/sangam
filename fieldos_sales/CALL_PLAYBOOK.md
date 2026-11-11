# How the AI caller keeps people on the line

Research notes (11 Nov 2026) and what was built from them. The goal: a call that feels like a polite, sharp young professional from Hyderabad ringing a builder, so the owner doesn't hang up, while still saying plainly that it is an AI.

## Why people hang up

1. **Dead air.** Callers sense a stall past roughly 0.8 seconds, and contact centres report about 40% more hang-ups when an agent takes over a second to respond ([Exotel](https://exotel.com/blog/achieve-low-latency-voice-ai-exotel/), [Retell](https://www.retellai.com/resources/sub-second-latency-voice-assistants-benchmarks), [Coval](https://www.coval.dev/blog/voice-ai-latency)). Our pipeline (speech-to-text, Claude, text-to-speech) takes about 2 to 3 seconds a turn, so the delay has to be hidden.
2. **The first ten seconds.** A generic pitch, no reason for the call, or no permission ask ends most cold calls ([echai](https://echai.ventures/gtm/gtm-outbound/my-cold-calls-die-in-the-first-ten-seconds-what-do-i-actually-say-when-they-pick-up), [Juno](https://junoschool.pages.dev/article/cold-call-opening-framework/)).
3. **Sounding like a script**: long sentences, lists, the same phrases, talking over the person, not reacting to what they said.
4. **Disrespect for their time or rank**: pitching when they're busy, arguing, rushing, getting the form of address wrong.

## What the agent now does

| Problem | Built |
|---|---|
| Dead air | A short acknowledgement ("जी।", "अच्छा।", "Okay.", "సరే అండి.") plays the moment the caller stops, while the reply is prepared. It is never the same twice in a row, and is skipped after a one-word answer. |
| Dead air | Replies are split into sentences and rendered in parallel; the first sentence plays as soon as it is ready. Fixed lines (greeting, goodbyes, the price answer) are pre-rendered and cached. One connection to Sarvam is reused. Claude runs with thinking off and low effort on calls. |
| Talking over people | The caller can interrupt: after about a quarter second of their speech, our audio stops at once (Exotel `clear`). The end-of-turn wait is 650 ms (`END_OF_TURN_MS`). |
| Silence | After 7 seconds of silence it asks once, "Hello, can you hear me?" |
| First ten seconds | Time-of-day greeting, their name with "ji"/"garu" when known, a named persona ("Priya", configurable) that says it's an AI, "here in Hyderabad" (local trust), one real detail from their website ("I saw your villa project in Kokapet"), then a permission ask: "Do you have two minutes?" |
| Script feel | Spoken style rules: 1 to 2 short sentences, react to what they said first, never reuse a phrase, no lists or symbols, numbers said the way people say them, two concrete slots offered ("Thursday 11 baje ya Friday 4 baje?"). |
| Language | Code-mixed like real speech: Hindi or Telugu with English business words. Hindi and Telugu go to the voice in their own script (Sarvam pronounces native script far better than romanised text, per its [Bulbul guide](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/best-practice-guide-for-bulbul-v-4-flash)). It switches the moment the caller does. Hindi verbs follow the persona's gender (`AGENT_GENDER`). |
| Respect | Busy or driving: no pitch, just "when shall I call back?". "Send details": agree and offer a one-minute WhatsApp video. Receptionist or accountant: extra polite, asks who handles site operations and when to reach them. Never argues; "not interested" ends the call warmly and permanently. |
| Trust | Answers "are you a robot?" with "Yes, honestly, I'm an AI assistant" and offers a person. Offers a visit to our Hi-Tech City office. |

## Why it still says it's an AI

Making it indistinguishable from a person is not the goal. It must disclose that it's an AI: honesty is the rule here, and an owner who later finds out a "person" was a bot won't trust FieldOS with their sites' money. What keeps people on the line is speed, relevance and respect, and those are all built in. The disclosure is one short, warm clause inside the greeting, not a legal notice.

## Worth testing in the first week (on your own phones first)

- **Voice**: try two Sarvam voices with `VOICE_VARIANTS` and keep the one with more booked walkthroughs (dashboard "Voice test" table). The default is `bulbul:v3` with `priya` (multilingual, and it matches the agent's name). A good second voice is `bulbul:v4-flash/simran_hi_sales`, a Hindi sales style that also reads English and Telugu cleanly (checked 2026-11-12). `anushka` no longer works with bulbul:v3, and bulbul:v2 is retired.
- **Pace**: `VOICE_PACE=1.05` (brisk but clear). Try 1.0 to 1.1.
- **When to call**: owners are usually reachable late morning (11 to 1) and late afternoon (3:30 to 6). Avoid Monday mornings and lunch. Calls already skip Saturdays (wage day on most sites) through `CALL_DAYS=Mon,Tue,Wed,Thu,Fri`; the dashboard's best-time grid shows which hours actually get answered.
- **End-of-turn wait**: if it cuts people off mid-sentence, raise `END_OF_TURN_MS` to 800; if it feels slow, try 550.
- Read 10 transcripts a day (`python -m fieldos_sales show <id>`) and note where people hung up. That is the best tuning data there is.

## Next step for even lower delay

Streaming speech (Sarvam's WebSocket text-to-speech and streaming speech-to-text) could bring a turn under a second. It needs live keys to build and test against, so it isn't done yet.
