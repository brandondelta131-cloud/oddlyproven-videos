// Step 5: verify date/time then press Schedule; returns the confirmation text (with the video link).
const EXPECT_DATE = "__DATE__", EXPECT_TIME = "__TIME__";
const sleep = ms => new Promise(r => setTimeout(r, ms));
const d = document.querySelector('ytcp-uploads-dialog'); const sch = d.querySelector('ytcp-visibility-scheduler');
const date = sch.innerText.split('\n').find(l => /\d{4}/.test(l)); const time = [...sch.querySelectorAll('input')].map(i => i.value).find(v => /:/.test(v));
if (date.trim() !== EXPECT_DATE || time !== EXPECT_TIME) throw new Error('schedule mismatch: ' + date + ' ' + time);
d.querySelector('#done-button').click(); await sleep(5000);
const dlg = document.querySelector('ytcp-video-share-dialog, ytcp-uploads-still-processing-dialog, tp-yt-paper-dialog[opened]');
const txt = dlg ? dlg.innerText.replace(/\n+/g, ' | ').slice(0, 400) : 'no dialog';
[...document.querySelectorAll('ytcp-button, button')].find(x => x.offsetParent && x.innerText.trim() === 'Close')?.click();
txt;
