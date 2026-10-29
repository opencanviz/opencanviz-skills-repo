# Launch reel scene reference

Every scene is an object with a `type` and that type's keys. Every key is optional unless
marked. Lengths are the most the layout holds before text shrinks or wraps.

```text
- logo: {bg}
- mascot: {bg}  (only when brand.mascot is true: a round smiley face reacting)
- headline: {lines: [1-2 lines, <= 26 chars each] (required), underline: a word from line 1, bg}
- pill_cycle: {lead: "<= 18 chars, ends mid-sentence", pills: [3 {label <= 24 chars, icon}], end: "<= 14 chars"}
- app_wall: {apps: [4-7 Iconify `logos:` refs of real tools the product works with], lines: [1-2 lines]}
- chat: {greeting, suggestions: [3-4 {icon, label <= 34 chars}], question <= 40 chars,
          status: [1-3 {icon, label like "Checking Stripe..."}], answer_title, answer: [3-4 lines <= 46 chars], bg}
- doc_edit: {icon, title <= 28 chars, subtitle, bullets: [2-3 short notes], prompt <= 30 chars,
              chip <= 24 chars (a referenced doc or setting), output: 2-3 sentences, <= 230 chars, bg}
- file_chat: {dashboard_title, file (with extension: .pdf .csv .xlsx .png .docx), question <= 40 chars,
               thinking, answer_title, answer: [3-4 lines <= 44 chars], bg}
- chips: {line <= 24 chars, chips: [2-3 {icon, label <= 18 chars}]}
- phone_chat: {suggestions: [2-3 {icon, label <= 30 chars}], prompt <= 42 chars, answer_title, answer: [3-5 lines <= 30 chars], bg}
- end: {cta <= 26 chars, tagline <= 26 chars}
- problem: {line <= 22 chars, pains: [3 pains the buyer has today, <= 40 chars each]}
- dashboard: {title, kpis: [3 {label <= 16 chars, value like "12,480" or "98%" or "$4.2k", delta like "+18%"}],
               chart_title, chart_note <= 18 chars, bg}
- terminal: {title, commands: [1-2 {cmd <= 44 chars, output: [1-3 lines <= 50 chars, start a good one with "✓"]}],
              done <= 32 chars, bg}  (developer products only)
- browser: {url, title <= 30 chars, subtitle <= 80 chars, cta <= 18 chars, nav: [3 short], features: [3 {icon, label <= 14 chars}], bg}
- split: {before_title, after_title, before: [3 old-way lines <= 30 chars], after: [3 new-way lines <= 30 chars]}
- stat: {value like "4.5x" or "90%" or "12,000" (required), label <= 30 chars, sub <= 50 chars, bg}
          (only a figure the description states or that is plainly a product setting; never an invented customer result)
- kanban: {columns: [3], cards: [4-6 {title <= 24 chars, col: 0|1|2}], move: index of the card dragged to the last column, bg}
- notifications: {line <= 22 chars, items: [3-4 {icon, title <= 26 chars, body <= 34 chars}]}
- map: {line <= 24 chars, pins: [3-6 {city (a major world city), label <= 18 chars}]}
- pricing: {plan, price like "$19", period like "/month", badge, features: [3-4 <= 28 chars], cta}
           (ONLY when the description states a price; copy it exactly)
- logo_grid: {line <= 26 chars, apps: [6-12 `logos:` refs of tools it integrates with]}
- compare: {line <= 24 chars, columns: [the alternative, product name], rows: [4-5 capabilities <= 30 chars],
             them: [true/false per row: does the alternative have it]}  (the alternative is "Typical tools" unless
             the description itself names the competitor; mark them true wherever a normal alternative has it,
             a table of all crosses is not believable)
- countdown: {line like "3 reasons to switch", items: [3 {icon, label <= 30 chars}] listed from 3 down to 1}
- feature_flash: {items: [4-6 {icon, label: one or two words}]}
- lineup: {line <= 26 chars, products: [2-6 {name, color hex, icon, desc <= 34 chars}]}
          (a suite or bundle of products, each named in the description; give each its own colour)
- receipt: {line <= 24 chars, title <= 24 chars, items: [2-6 {name, price}], total, new_price, new_label <= 22 chars}
           (what the buyer pays today for the tools this replaces. ONLY tools and prices the description
           names, copied exactly; leave total out unless the description states it)
- snippet: {line <= 24 chars, label (a file name), code: ONE line of install code <= 90 chars, status <= 18 chars}
- inbox: {line <= 24 chars, items: [3-4 {from, subject <= 30 chars, preview <= 60 chars}], open: index}
         (email products, or products whose output arrives as email)
- funnel: {line <= 24 chars, stages: [3-5 {label <= 16 chars, value like "12,480"}]}  (sample data, falling)
- toggle: {line <= 24 chars, title, items: [3-5 {label <= 30 chars, sub <= 40 chars}]}  (settings being switched on)
- form_builder: {line <= 24 chars, title, fields: [3-4 {label, type: text|email|select|date|number|phone|file}], button, done}
- repo: {line <= 24 chars, name "owner/repo", desc <= 90 chars, license, language, stars}
        (ONLY when the description says it is open source; stars and license only if stated)
- timeline: {line <= 24 chars, items: [3-5 {date, label <= 24 chars}]}  (ONLY dates the description states)
- quote: {quote, author, role}  (ONLY a sentence quoted word for word from the description)
- phone_app: {line <= 24 chars, title <= 20 chars, value like "12.4 km" or "21°", value_label <= 22 chars,
               rows: [3-4 {icon, label <= 20 chars, value <= 10 chars}], alert: {title <= 26 chars, body <= 34 chars}, bg}
               (mobile apps and hardware companion apps; a phone screen with no AI in it)
- screenshot: {caption <= 34 chars, frame: browser|phone|none, url, focus: [1-3 {x, y in 0-1, zoom 1.4-2.4, label <= 20 chars}]}
              (ONLY when the user supplied a screenshot; the image is attached by the tool)

Any UI scene may also take product: {name, color} to show which product of a suite it belongs to; it
then plays in that product's colour.

bg is one of "paper", "accent1", "accent2", "accent3". Product UI scenes sit on an accent; headlines on paper.
```

## Icons

ICONS are Iconify refs. Interface glyphs: Phosphor, `ph:<name>-bold` or `ph:<name>-fill`, common names only
(sparkle, lightning, brain, list-bullets, list-checks, question, pencil-simple-line, magnifying-glass,
microphone, chart-bar, chart-line, currency-dollar, users, user-plus, link, gift, envelope, calendar,
bell, file-text, code, terminal, rocket, shield-check, globe, clock, chat-circle, megaphone, storefront,
credit-card, handshake, trophy, target, funnel, database, cloud, gear). Brand logos: `logos:<name>`
(slack-icon, google-drive, figma, github-icon, notion-icon, shopify, salesforce,
zapier-icon, google-gmail, microsoft-teams, jira, linear-icon, dropbox, asana-icon, intercom-icon,
mailchimp-freddie, wordpress-icon, paypal, google-analytics, discord-icon, vercel-icon). Square marks
only: wordmarks such as logos:stripe, logos:hubspot, logos:webflow or logos:aws are unreadable at icon size.

These and about 650 more are bundled; `python3 scripts/build.py --icons <text>` lists the matches. An icon that is not bundled draws as a sparkle unless the build runs with `--fetch-icons`.

## Claims

Mock UI (dashboard KPIs, funnel stages, inbox mail, kanban cards, chat answers) is sample data
and may be invented, with plausible invented names. Claims are not: these scenes must use only
what the sources state, and `build.py` checks them before it builds.

| Scene | What must be in the sources |
| --- | --- |
| stat | the figure itself (digits or words: "two minutes" supports "2 min") |
| pricing | the price, copied exactly |
| receipt | every tool name and its price; the total only if stated |
| compare | a named competitor (otherwise use "Typical tools") |
| lineup | every product name |
| repo | that it is open source; stars and license only if stated |
| timeline | every date |
| quote | the sentence, word for word |
| chat, phone_chat, file_chat | the product has an assistant, chat, copilot or agent |
| doc_edit, pill_cycle | the product writes, drafts or generates |
| screenshot | a screenshot passed with `--screenshot` |
