// Source: WebRPA@5ccb900e, components/workflow/documentation/content-module-reference.en.ts; see SOURCE.md for license and adaptation boundaries.
export const moduleReferenceContentEn = `# Module Reference

This page walks through the modules by sidebar category, for when you know what you want to do but not which module does it.
Each group starts with what it is for and how modules combine, then lists the modules. For full configuration details and worked examples, jump to the matching topic guide.

> Three ways to find a module: (1) browse by category here; (2) type Chinese, pinyin or pinyin initials into the module search box on the left (typing \`dkwy\` finds "Open page"); (3) ask the AI assistant "which module do I use to do X".

---

## Additional web automation modules

### Page navigation

Page-level operations that go with "Open page". Iframes are the usual trap: an embedded iframe is a separate document, and until you switch into it you will never find the elements inside.

| Module | What it does |
|------|------|
| Close page | Closes the current tab, usually at the end of a workflow to free resources |
| Switch iframe | Enters the given iframe; later element operations apply inside it |
| Switch back to main page | Leaves the iframe; forgetting this makes later main-page elements unreachable |
| Page load complete | Writes the load state into a variable for conditions; does not block the flow |

### Element interaction and queries

"Element exists" and "Element visible" write a boolean into a variable, which is the basis of robust flows: check first, then act, instead of clicking an element that has not appeared yet.

| Module | What it does |
|------|------|
| Checkbox | Checks / unchecks a box by target state rather than blind clicking |
| Element exists | Whether the element is present in the DOM, result into a variable |
| Element visible | Whether the element is visible (false when present but hidden) |
| Extract table data | Reads an entire HTML table into a list, far faster than cell-by-cell |

### Data collection: network monitoring

When the data on screen cannot be scraped (filled in by JS, or paging goes through an API), listening to the responses is more reliable. The three modules are used together in order.

| Module | What it does |
|------|------|
| Start network monitor | Turns on monitoring; requests from then on are recorded |
| Wait for API request | Blocks until a request matching the URL completes, response body into a variable |
| Stop network monitor | Turns monitoring off and frees resources |

Typical order: Start network monitor → Click element (triggers the request) → Wait for API request → Stop network monitor.

### DP anti-detection automation

Use this set (built on DrissionPage) when normal browser automation gets flagged by a site's bot protection. It behaves closer to a real user, at the cost of fewer advanced capabilities. These modules form their own stack — do not mix them with the regular web modules on the same page.

| Module | What it does |
|------|------|
| DP open page | Starts the DP browser and opens a URL |
| DP click element | Clicks (CSS / XPath locators) |
| DP input text | Types into an input box |
| DP get text | Reads element text into a variable |
| DP get HTML | Reads element or page HTML into a variable |
| DP run JS | Runs JavaScript in page context |
| DP wait element | Waits for an element so actions are not too early |
| DP scroll page | Scrolls the page, used to trigger lazy loading |
| DP close browser | Closes the DP browser and frees the process |

---

## Additional desktop and screen automation modules

### Image recognition and text clicking

The fallback when neither web nor desktop element locating works (Flash, Canvas, remote desktop views). The downside is dependence on screen resolution and theme, so it breaks easily across machines — keep it below element locating in priority.

| Module | What it does |
|------|------|
| Click text | OCRs the screen for the given text and clicks it |
| Hover text | Finds the text and hovers over it (to open hover menus) |

### Screen and recording

| Module | What it does |
|------|------|
| Record screen | Records the screen to a video file, often to keep evidence of a failed run |

### Desktop application control operations

This whole set is the core of Windows desktop automation (built on UIAutomation). The pattern is fixed: get an application handle variable via "Start application" or "Connect application", get a control handle variable via "Find control", then base every operation on those two handles.

| Module | What it does |
|------|------|
| Window state control | Minimize / maximize / restore a window |
| Input text into control | Writes text into input-type controls (steadier than simulating the keyboard) |
| Get control text | Reads the control's displayed text into a variable |
| Set control value | Sets the control's value directly (dropdowns, spin boxes, etc.) |
| Operate radio button | Selects the given radio button |
| Send hotkey | Sends a key combination to the control (e.g. Ctrl+S) |
| Get control property | Reads any UIAutomation property into a variable |
| Batch extract list | Reads all rows of a list / table control into a list at once |
| Application state snapshot | Captures a summary of the current control tree, very useful when locating fails |
| Find control by XPath | Locates controls with XPath-like syntax, good for deep trees without unique identifiers |
| Select and extract text | Selects text inside a control and extracts it, for controls whose text cannot be read directly |
| Scroll control | Scrolls a list / panel control to load more content |

> When a control cannot be located, work through this order: (1) use "Application state snapshot" to see what it is actually called in the control tree; (2) use "Wait for control" instead of finding it immediately; (3) switch to "Find control by XPath" and locate by hierarchy.

### Phone automation

| Module | What it does |
|------|------|
| Click text | Finds the given text on the phone screen and taps it (connect the device first) |

---

## Additional flow control and trigger modules

### Flow control

| Module | What it does |
|------|------|
| Infinite loop | Loops until "Break loop" stops it. The index variable defaults to \`loop_index\` (note the "Loop" module defaults to \`index\`); always write a working exit condition inside the body |
| Assertion / checkpoint | Verifies a variable / element / expression against expectations, then aborts or just records depending on configuration. Use it to produce readable results in automated testing |
| Force stop workflow | Ends the whole workflow immediately; you can log a stop reason |
| Run another workflow | Runs another workflow file as a sub-flow, for reuse and for splitting large flows |

### Triggers

| Module | What it does |
|------|------|
| Gesture trigger | Uses the camera to recognise a gesture and trigger the flow, with configurable confidence threshold and timeout; the result goes into a variable |

---

## Additional data processing modules

### List operations

List modules follow one convention: input is a list variable name, output goes into a result variable. They never modify the original list, which makes chaining easy.

| Module | What it does |
|------|------|
| Export list | Writes the list to a file (CSV / JSON, etc.) |
| Sum list | Sums a numeric list |
| Average list | Averages a numeric list |
| Max of list | Takes the maximum |
| Min of list | Takes the minimum |
| Sort list | Ascending / descending, optionally by field |
| Deduplicate list | Removes duplicate elements |
| Slice list | Takes a sub-list by start and end index |
| Reverse list | Reverses the order |
| Find in list | Finds an element and returns its index or the element |
| Count list | Counts occurrences of an element |
| Filter list | Keeps elements matching a condition |
| Map list | Applies one transformation to every element |
| Flatten list | Flattens nested lists into one level |
| Chunk list | Splits into fixed-size groups, handy for batch processing |
| Remove empty from list | Drops empty strings / null elements |
| List intersection | Elements present in both lists |
| List union | Merges two lists and deduplicates |
| List difference | Elements only in the first list |
| List cartesian product | Every combination of two lists |
| Shuffle list | Randomises the order |
| Sample list | Picks N random elements |
| List to string (advanced) | Joins with a separator, with optional prefix/suffix and field selection |

### Dictionary operations

| Module | What it does |
|------|------|
| Dict keys | Takes all keys as a list |
| Merge dicts | Merges two dicts; the second overrides same-named keys |
| Filter dict | Keeps entries matching a condition |
| Map dict values | Applies one transformation to every value |
| Invert dict | Swaps keys and values |
| Sort dict | Sorts by key or value |
| Deep copy dict | Copies a dict so the two are independent |
| Get dict path | Reads a nested value via a path like \`a.b.c\`, easier than level-by-level access |
| Flatten dict | Flattens a nested dict into one level with path-style keys |

> When handling JSON from an API, "Get dict path" plus "Flatten dict" is the most useful pair: the first pulls one exact field, the second shows you the whole structure at once.

### Math and statistics

| Module | What it does |
|------|------|
| Modulo | Remainder |
| Nth root | Any root (square root by default) |
| Power | Any exponent |
| Logarithm | Custom base supported |
| Exponential | Natural exponential |
| Permutation and combination | Computes permutations / combinations |
| Clamp number | Clamps a value into [min, max] to prevent out-of-range values |
| Random number (advanced) | Integer / float, with distribution and precision options |
| Normalize data | Scales a set of numbers into 0–1 |
| Standardize data | Z-score transformation using mean and standard deviation |

---

## Additional Excel modules

The full Excel tutorial lives in the "Excel automation" topic; this section only covers what the quick reference did not.

| Module | What it does |
|------|------|
| Add sheet | Creates a sheet |
| Delete sheet | Deletes the given sheet |
| Insert rows | Inserts blank rows at a position |
| Insert columns | Inserts blank columns at a position |
| Delete columns | Deletes the given columns |
| Read formula / value | The key setting is "read content": choose "value" for the computed result, "formula" for text like \`=SUM(A1:A9)\`. Getting a formula string instead of a number means this option is set wrong |
| Set hyperlink | Adds a link to a cell |
| Set comment | Adds a comment to a cell |
| First empty column | Finds the first empty column, used for appending data |
| First empty cell | Finds the first empty cell, used to locate the write position |

---

## Database modules

All seven database families share the same structure, so learning one teaches you all: **connect → operate → disconnect**. The connect module writes a connection handle into a variable, later modules find the connection through it, and you must disconnect at the end to release it.

> Shared notes:
> - Query modules produce a list-of-dicts structure that feeds straight into "Foreach list" for row-by-row processing.
> - Write modules return the affected row count, which you can verify with "Assertion / checkpoint".
> - When interpolating variables into SQL, mind injection risk: prefer the module's parameter fields over hand-built strings.
> - Disconnect even when the flow exits abnormally: put the disconnect at the end of the workflow and clean up before "Force stop workflow".

### MySQL

| Module | What it does |
|------|------|
| MySQL connect | Opens a connection and writes the connection variable |
| MySQL query | Runs a SELECT, result into a variable |
| MySQL execute SQL | Runs arbitrary SQL (DDL, bulk updates, etc.) |
| MySQL insert | Inserts by table and fields, no SQL needed |
| MySQL update | Updates by condition |
| MySQL delete | Deletes by condition |
| MySQL close | Releases the connection |

### Oracle

| Module | What it does |
|------|------|
| Oracle connect | Opens a connection |
| Oracle query | Runs a query |
| Oracle execute SQL | Runs arbitrary SQL |
| Oracle insert | Inserts a record |
| Oracle update | Updates records |
| Oracle delete | Deletes records |
| Oracle disconnect | Releases the connection |

### PostgreSQL

| Module | What it does |
|------|------|
| PostgreSQL connect | Opens a connection |
| PostgreSQL query | Runs a query |
| PostgreSQL execute SQL | Runs arbitrary SQL |
| PostgreSQL insert | Inserts a record |
| PostgreSQL update | Updates records |
| PostgreSQL delete | Deletes records |
| PostgreSQL disconnect | Releases the connection |

### SQL Server

| Module | What it does |
|------|------|
| SQL Server connect | Opens a connection |
| SQL Server query | Runs a query |
| SQL Server execute SQL | Runs arbitrary SQL |
| SQL Server insert | Inserts a record |
| SQL Server update | Updates records |
| SQL Server delete | Deletes records |
| SQL Server disconnect | Releases the connection |

### SQLite

No server required — it connects to a local file, which makes it a good scratch store for the workflow itself.

| Module | What it does |
|------|------|
| SQLite connect | Opens the database file (created if missing) |
| SQLite query | Runs a query |
| SQLite execute SQL | Runs arbitrary SQL |
| SQLite insert | Inserts a record |
| SQLite update | Updates records |
| SQLite delete | Deletes records |
| SQLite disconnect | Closes the file |

### MongoDB

A document database: you work with collections and documents, no SQL involved.

| Module | What it does |
|------|------|
| MongoDB connect | Opens a connection |
| MongoDB find | Queries documents by condition |
| MongoDB insert | Inserts a document |
| MongoDB update | Updates documents |
| MongoDB delete | Deletes documents |
| MongoDB disconnect | Releases the connection |

### Redis

Key-value storage, commonly used to pass state between workflows, hold dedup sets, or keep simple counters.

| Module | What it does |
|------|------|
| Redis connect | Opens a connection |
| Redis get | Reads a value by key |
| Redis set | Writes a value by key (expiry optional) |
| Redis delete | Deletes a key |
| Redis hash get | Reads a field from a hash |
| Redis hash set | Writes a hash field |
| Redis disconnect | Releases the connection |

---

## Additional document and file modules

### PDF processing

| Module | What it does |
|------|------|
| Rotate PDF pages | Rotates the given pages by an angle (fixes scans that came in sideways) |

### Document format conversion

This whole batch runs on one conversion engine with the same configuration pattern: input path plus output path. Conversion quality depends on how well-formed the source is; a heavily styled Word file losing formatting when converted to Markdown is expected.

| Module | What it does |
|------|------|
| Markdown to HTML | Produces an HTML fragment |
| HTML to Markdown | Converts page body text to Markdown |
| Markdown to PDF | Produces a PDF (good for reports) |
| Markdown to Word | Produces a .docx |
| Word to Markdown | Extracts Word body text as Markdown |
| HTML to Word | Web page to .docx |
| Word to HTML | .docx to a web page |
| Markdown to EPUB | Produces an e-book |
| EPUB to Markdown | E-book to Markdown |
| LaTeX to PDF | Compiles a LaTeX source file |
| RST to HTML | reStructuredText to HTML |
| Org to HTML | Org-mode to HTML |

---

## Additional media processing modules

### Image editing

| Module | What it does |
|------|------|
| Grayscale image | Converts to grayscale |
| Round image corners | Adds rounded corners (radius configurable) |

### Video processing

| Module | What it does |
|------|------|
| Rotate video | Rotates by an angle |
| Video speed | Speeds up / slows down playback |
| Extract frame | Grabs the frame at a given moment as an image |
| Add subtitles | Burns subtitles in or attaches them as soft subtitles |
| Resize video | Scales the video dimensions |

### Audio processing

| Module | What it does |
|------|------|
| Adjust volume | Raises / lowers the volume |

### Media format conversion

| Module | What it does |
|------|------|
| Video to audio | Extracts the audio track to a file |
| Video to GIF | Converts to GIF (longer clips mean much larger files) |

---

## Additional AI modules

### AI vision action

| Module | What it does |
|------|------|
| AI vision action | Give a natural-language instruction (such as "click the login button") and the AI looks at a screenshot to decide where to click and does it. The fallback when both element locating and image recognition fail; accuracy depends on the model in use |

### AI generation

| Module | What it does |
|------|------|
| AI generate image | Generates an image from a prompt, result path into a variable |
| AI generate video | Generates a video from a prompt (slow — set a generous timeout) |

### AI scraping

| Module | What it does |
|------|------|
| AI smart scraper (experimental) | Give a URL and a sentence describing what you need; the AI decides how and what to scrape |
| AI element selector (experimental) | Give a description and the AI produces a selector, for pages where selectors are hard to write |
| AI single-page scrape | Scrapes one page and returns structured output |
| AI site link scrape | Collects the link inventory of a site |
| AI full-site scrape | Crawls the whole site by rules |

> The two "experimental" modules give unstable results and suit the exploration stage. For production flows, use them to work out the page structure first, then switch to regular modules with fixed selectors.

---

## Additional network and integration modules

### Network requests

| Module | What it does |
|------|------|
| Webhook request | Sends an HTTP request (method, headers and body all configurable); body, status code and response headers each go into their own variable |

### Notifications

The dozen-plus channels share one configuration pattern: server address or token, plus message content. Which one you pick depends on what your team already uses.

| Module | What it does |
|------|------|
| Discord notify | Posts to a Discord channel |
| Telegram notify | Posts to Telegram (bot token and chat ID required) |
| Bark notify | Pushes to the Bark client on iOS |
| Slack notify | Posts to a Slack channel |
| Teams notify | Posts to Microsoft Teams |
| Pushover notify | Pushes via Pushover |
| PushBullet notify | Pushes via PushBullet |
| Gotify notify | Pushes to a self-hosted Gotify server |
| ServerChan notify | Pushes to WeChat via ServerChan |
| PushPlus notify | Pushes to WeChat via PushPlus |
| Webhook notify | Pushes to any custom webhook URL |
| Ntfy notify | Pushes to an ntfy topic (self-hostable) |
| Matrix notify | Posts to a Matrix room |
| RocketChat notify | Posts to a Rocket.Chat channel |

### Notifications and logs

| Module | What it does |
|------|------|
| System notification | Shows a Windows system notification (title plus body) to alert the local user |

### QQ bot

Configure the NapCat connection first — see the "Chat bots" topic.

| Module | What it does |
|------|------|
| QQ friend list | Pulls the friend list into a variable |
| QQ group list | Pulls the group list into a variable |
| QQ group members | Pulls the member list of a given group |
| QQ login info | Reads the logged-in account info, useful to verify the connection |

### Feishu and WPS multi-dimensional tables

| Module | What it does |
|------|------|
| Feishu bitable write | Appends / updates records in a Feishu bitable |
| WPS bitable read | Reads WPS bitable data into a variable |
| WPS bitable write | Writes data into a WPS bitable |

### SSH remote

| Module | What it does |
|------|------|
| SSH upload file | Sends a local file to the remote host |
| SSH download file | Pulls a remote file to the local machine |
| SSH disconnect | Closes the SSH session |

### LAN sharing

| Module | What it does |
|------|------|
| Share folder on network | Shares a local folder on the LAN |
| Share file on network | Shares a single file |
| Stop network share | Cancels the share |
| Start screen share | Shares this machine's screen on the LAN for others to view |

### SAP automation

Log in with "SAP login" first to get the session variable — every later module uses it to find the session. Get element IDs from SAP's own script recorder.

| Module | What it does |
|------|------|
| SAP logout | Logs out and ends the session |
| Close warning dialog | Dismisses a warning box blocking the flow |
| Set combo box | Selects a dropdown option |
| Switch tab | Switches to the given tab (element ID starts with \`tabp\`); controls inside that tab are unreachable until you switch to it |
| Export grid to Excel | Exports a GridView table to an Excel file |

---

## Additional utility modules

### Encryption and encoding

| Module | What it does |
|------|------|
| MD5 hash | Computes an MD5 digest |
| SHA hash | Computes a SHA-family digest |
| URL encode / decode | URL escaping and unescaping |
| UUID generator | Generates a UUID; the default variable name is \`uuid\` |

### Color and time conversion

| Module | What it does |
|------|------|
| RGB to HSV | Color space conversion |
| RGB to CMYK | Converts to print color values |
| HEX to CMYK | Hex color to print color values |

---

## When you cannot find the module you want

1. Search the sidebar by **capability words** first ("compress", "dedup", "screenshot"); keywords beyond the module name also match.
2. Then ask the AI assistant: describe the goal ("dedup phone numbers in this Excel file and write them back") and it will suggest a module combination.
3. If there really is no matching module, wrap a piece of Python / JS logic into a reusable module with "Custom module", or write the logic directly with "Run Python script".
`
