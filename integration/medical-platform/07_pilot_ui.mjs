import {attachMedicalPilot} from './072_ui_adapter.mjs';
const get=id=>document.getElementById(id);
const status=text=>{get('status').textContent=text;};
const app=location.pathname.endsWith('/terapevt')?'terapevt':'nmp';
try {
  const pilot=await attachMedicalPilot({enabled:sessionStorage.getItem('medical-platform-pilot')==='1',app});
  if (!pilot) throw Error('Unsupported pilot context');
  get('pilot-controls').disabled=false;
  pilot.resume().then(ok=>{if(ok) status('Сессия восстановлена.');}).catch(()=>{});
  const handle=fn=>async event=>{
    event.preventDefault();
    try { await fn(event); } catch { status('Операция недоступна. Проверьте сеть, вход и права.'); }
  };
  get('login').onsubmit=handle(async ({target})=>{
    const data=new FormData(target);
    get('quiz')?.replaceChildren();
    if (get('quiz')) get('quiz').onsubmit=null;
    target.elements.password.value='';
    await pilot.login(data.get('email'),data.get('password'));
    status('Вход выполнен.');
  });
  get('logout').onclick=handle(async ()=>{
    get('quiz')?.replaceChildren();
    if (get('quiz')) get('quiz').onsubmit=null;
    await pilot.logout();
    status('Вы вышли.');
  });
  if (app==='nmp') {
    get('load').onsubmit=handle(async ({target})=>{
      const {test,owner}=await pilot.test(new FormData(target).get('test'));
      const quiz=get('quiz'), attempt_id=crypto.randomUUID();
      quiz.replaceChildren();
      for (const q of test.questions) {
        const field=document.createElement('fieldset'), title=document.createElement('legend');
        title.textContent=q.prompt;
        field.append(title);
        q.options.forEach((text,choice)=>{
          const label=document.createElement('label'), input=document.createElement('input');
          Object.assign(input,{name:q.question_id,type:'radio',value:String(choice),required:true});
          label.append(input,document.createTextNode(text));
          field.append(label,document.createElement('br'));
        });
        quiz.append(field);
      }
      const save=document.createElement('button');
      save.textContent='Сохранить попытку';
      quiz.append(save);
      quiz.onsubmit=handle(async ()=>{
        save.disabled=true;
        try {
          const choices=new FormData(quiz);
          await pilot.enqueue({test_id:test.test_id,test_version:test.test_version,attempt_id,
            answers:test.questions.map(q=>({question_id:q.question_id,choice:Number(choices.get(q.question_id))}))},owner);
          quiz.replaceChildren();
          status('Попытка сохранена на устройстве.');
        } finally { save.disabled=false; }
      });
    });
    get('sync').onclick=handle(async ()=>{
      const waiting=await pilot.drain();
      status(waiting.length ? 'В очереди: '+waiting.map(row=>row.state).join(', ') : 'Очередь пуста.');
    });
  }
} catch { status('Стенд недоступен в этом браузере.'); }
