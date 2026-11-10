// Step 4: focus the time field. THEN real keyboard: ctrl+a, type "14:00", Return.
const sch = document.querySelector('ytcp-uploads-dialog ytcp-visibility-scheduler');
const t = [...sch.querySelectorAll('input')].find(x => /^\d{1,2}:\d\d/.test(x.value)); t.focus(); t.select();
JSON.stringify({ date: sch.innerText.split('\n')[0], time: t.value, focused: document.activeElement === t });
