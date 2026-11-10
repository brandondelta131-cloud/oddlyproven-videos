// Step 3: move to Visibility, expand Schedule, open the date picker and focus its text field.
// THEN with real keyboard actions (browser computer tool): ctrl+a, type e.g. "11 Nov 2026", Return.
const sleep = ms => new Promise(r => setTimeout(r, ms));
const d = document.querySelector('ytcp-uploads-dialog');
for (let i = 0; i < 3 && !d.querySelector('ytcp-uploads-review'); i++) { d.querySelector('#next-button').click(); await sleep(2500); }
d.querySelector('#second-container-expand-button')?.click(); await sleep(1500);
const sch = d.querySelector('ytcp-visibility-scheduler');
sch.querySelector('#datepicker-trigger, ytcp-text-dropdown-trigger').click(); await sleep(1200);
const i = document.querySelector('ytcp-date-picker input'); i.focus(); i.select();
JSON.stringify({ checks: d.querySelector('ytcp-uploads-checks')?.innerText.replace(/\n+/g, ' ').slice(0, 160), focused: document.activeElement === i, current: i.value });
