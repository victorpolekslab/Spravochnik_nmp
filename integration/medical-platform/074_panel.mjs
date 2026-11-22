import {attachMedicalPilot} from './072_ui_adapter.mjs';

const panels = new Map();
const shell = '<h2>Общий вход</h2><form data-login><label>Email <input name="email" type="email" required autocomplete="username"></label> <label>Пароль <input name="password" type="password" required autocomplete="current-password"></label> <button>Войти</button></form><button data-logout type="button">Выйти</button> <button data-off type="button">Отключить пилот</button><p data-status role="status"></p>';
const learning = '<h3>Серверные тренировочные задания</h3><form data-load><label>Тест <input name="test" value="course:gbn" required></label> <button>Загрузить</button></form><form data-quiz></form><button data-sync type="button">Синхронизировать</button>';

function build(app) {
  const panel = document.createElement('section');
  panel.className='calc-card';
  panel.dataset.medicalPlatform=app;
  // The markup is constant. Catalog content below is rendered as text.
  panel.innerHTML=shell+(app==='nmp'?learning:'');
  const find=name=>panel.querySelector('[data-'+name+']');
  const status=message=>{find('status').textContent=message;};
  const ready=attachMedicalPilot({enabled:true,app}).then(pilot=>{
    if (!pilot) throw Error('UNSUPPORTED');
    void pilot.resume().then(ok=>{if(ok)status('Сессия восстановлена.');}).catch(()=>{});
    return pilot;
  });
  ready.catch(()=>status('Пилот недоступен. Основные разделы работают в прежнем режиме.'));
  let busy=false;
  const bind=(node,event,fn)=>node.addEventListener(event,async e=>{
    e.preventDefault();
    if(busy)return;
    busy=true;
    try{await fn(await ready,e);}
    catch{status('Операция недоступна. Проверьте вход, права и сеть.');}
    finally{busy=false;}
  });
  function clearQuiz(){
    const quiz=find('quiz');
    if(quiz){quiz.replaceChildren();quiz.onsubmit=null;}
  }
  find('off').onclick=()=>{sessionStorage.removeItem('medical-platform-pilot');location.reload();};
  bind(find('login'),'submit',async(pilot,event)=>{
    const form=event.currentTarget || find('login');
    const data=new FormData(form);
    form.elements.password.value='';
    clearQuiz();
    await pilot.login(data.get('email'),data.get('password'));
    status('Вход выполнен.');
  });
  bind(find('logout'),'click',async pilot=>{
    clearQuiz();
    await pilot.logout();
    status('Вы вышли.');
  });
  if(app==='nmp'){
    bind(find('load'),'submit',async pilot=>{
      const {test,owner}=await pilot.test(new FormData(find('load')).get('test'));
      const quiz=find('quiz'), attempt_id=crypto.randomUUID();
      clearQuiz();
      for(const question of test.questions){
        const field=document.createElement('fieldset'), title=document.createElement('legend');
        title.textContent=question.prompt;
        field.append(title);
        question.options.forEach((option,choice)=>{
          const label=document.createElement('label'), input=document.createElement('input');
          Object.assign(input,{type:'radio',name:question.question_id,value:String(choice),required:true});
          label.append(input,document.createTextNode(option));
          field.append(label);
        });
        quiz.append(field);
      }
      const save=document.createElement('button');
      save.textContent='Сохранить попытку';
      quiz.append(save);
      quiz.onsubmit=async event=>{
        event.preventDefault();
        if(busy)return;
        busy=true;
        save.disabled=true;
        try{
          const choices=new FormData(quiz);
          await pilot.enqueue({test_id:test.test_id,test_version:test.test_version,attempt_id,
            answers:test.questions.map(q=>({question_id:q.question_id,choice:Number(choices.get(q.question_id))}))},owner);
          clearQuiz();
          status('Попытка сохранена на устройстве.');
        }catch{status('Не удалось сохранить попытку. Проверьте активную учётную запись и хранилище.');}
        finally{busy=false;save.disabled=false;}
      };
    });
    bind(find('sync'),'click',async pilot=>{
      const waiting=await pilot.drain();
      status(waiting.length?'Попыток в очереди: '+waiting.length:'Очередь пуста.');
    });
  }
  return panel;
}

export function mountMedicalPanel(container,app) {
  if(!panels.has(app))panels.set(app,build(app));
  const panel=panels.get(app);
  if(panel.parentNode!==container)container.prepend(panel);
}
