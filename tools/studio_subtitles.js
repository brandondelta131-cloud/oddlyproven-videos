// Step 2 (after studio_details.js): go to "Video elements", upload the English .srt from GitHub raw.
const SRT_URL = "__SRT_URL__";
const sleep = ms => new Promise(r => setTimeout(r, ms));
const d = document.querySelector('ytcp-uploads-dialog');
d.querySelector('#next-button').click(); await sleep(2500);
const srt = await (await fetch(SRT_URL)).text();
const file = new File([srt], SRT_URL.split('/').pop(), { type: 'application/x-subrip' });
const addBtn = d.querySelector('#subtitles-button') || [...d.querySelectorAll('ytcp-button, button')].filter(x => x.innerText.trim() === 'Add')[1];
addBtn.click(); await sleep(2500);
[...document.querySelectorAll('button')].find(x => x.offsetParent && x.innerText.trim() === 'Upload file').click(); await sleep(2000);
const orig = HTMLInputElement.prototype.click; window.__picked = false;
HTMLInputElement.prototype.click = function () {
  if (this.type === 'file') { const dt = new DataTransfer(); dt.items.add(file); this.files = dt.files; this.dispatchEvent(new Event('change', { bubbles: true })); window.__picked = true; HTMLInputElement.prototype.click = orig; return; }
  return orig.call(this);
};
[...document.querySelectorAll('tp-yt-paper-radio-button')].find(x => x.offsetParent && x.innerText.trim() === 'With timing').click(); await sleep(500);
[...document.querySelectorAll('ytcp-button, button')].filter(x => x.offsetParent && x.innerText.trim() === 'Continue').pop().click(); await sleep(4000);
[...document.querySelectorAll('ytcp-button, button')].filter(x => x.offsetParent && x.innerText.trim() === 'Done').pop()?.click(); await sleep(2500);
const ve = d.querySelector('ytcp-uploads-video-elements, ytcp-video-elements');
JSON.stringify({ picked: window.__picked, srtChars: srt.length, subtitles: ve ? /by you/.test(ve.innerText) : null });
