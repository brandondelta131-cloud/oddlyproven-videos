// Run in YouTube Studio's upload page (…/videos/upload?d=ud) via the built-in browser javascript tool.
// Replace the three __PLACEHOLDERS__ before running. Uploads the video from GitHub raw,
// fills title + description, Not made for kids, Altered/synthetic = Yes, no paid promotion.
const VIDEO_URL = "__VIDEO_URL__";      // https://raw.githubusercontent.com/brandondelta131-cloud/oddlyproven-videos/main/queue/<slug>.mp4
const TITLE = __TITLE_JSON__;           // JSON string literal
const DESCRIPTION = __DESC_JSON__;      // JSON string literal
const sleep = ms => new Promise(r => setTimeout(r, ms));
let inp; for (let i = 0; i < 20 && !(inp = document.querySelector('input[type=file]')); i++) await sleep(500);
if (!inp) throw new Error('no file input: open …/videos/upload?d=ud first');
const resp = await fetch(VIDEO_URL); if (!resp.ok) throw new Error('fetch ' + resp.status);
const blob = await resp.blob();
const file = new File([blob], VIDEO_URL.split('/').pop(), { type: 'video/mp4' });
const dt = new DataTransfer(); dt.items.add(file); inp.files = dt.files;
inp.dispatchEvent(new Event('change', { bubbles: true }));
let d, boxes = [];
for (let i = 0; i < 40; i++) { await sleep(500); d = document.querySelector('ytcp-uploads-dialog'); boxes = d ? [...d.querySelectorAll('#textbox[contenteditable]')] : []; if (boxes.length >= 2) break; }
if (boxes.length < 2) throw new Error('details form not found');
await sleep(1500);
function setBox(el, txt) { el.focus(); document.execCommand('selectAll', false, null); document.execCommand('insertText', false, txt); el.dispatchEvent(new Event('input', { bubbles: true })); }
setBox(boxes[0], TITLE); await sleep(300); setBox(boxes[1], DESCRIPTION);
d.querySelector('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').click();
d.querySelector('#toggle-button')?.click(); await sleep(1500);
d.querySelector('tp-yt-paper-radio-button[name="VIDEO_HAS_ALTERED_CONTENT_YES"]').click();
const np = d.querySelector('tp-yt-paper-radio-button[name="VIDEO_PAID_PRODUCT_PLACEMENT_NO"]'); if (np && np.getAttribute('aria-checked') !== 'true') np.click();
await sleep(500);
JSON.stringify({ size: blob.size, title: boxes[0].innerText, descStart: boxes[1].innerText.slice(0, 40),
  notKids: d.querySelector('[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').getAttribute('aria-checked'),
  altered: d.querySelector('[name="VIDEO_HAS_ALTERED_CONTENT_YES"]').getAttribute('aria-checked'),
  language: d.querySelector('#language-input')?.innerText.replace(/\n/g, ' '), category: d.querySelector('#category')?.innerText });
