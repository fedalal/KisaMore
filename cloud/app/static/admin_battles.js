(function(){
  if(typeof titles!=="undefined"){
    titles.battles=["Битвы растений","Полка, участники, ресурсы и действия соревнования"];
  }

  var oldSelect=selectSection;
  selectSection=function(name){
    oldSelect(name);
    if(name==="battles"){
      loadOptions();
      loadBattles();
    }
  };

  var form=document.getElementById("battleCreateForm");
  var rack=document.getElementById("battleRack");
  var plant=document.getElementById("battlePlant");
  var body=document.getElementById("battlesBody");
  var actions=document.getElementById("battleActionsBody");
  var editDialog=document.getElementById("battleEditDialog");
  var editForm=document.getElementById("battleEditForm");
  var battleRows={};

  function status(s){
    var m={
      open:"Набор",
      ready_to_plant:"Нужно посадить",
      planting:"Посадка",
      growing:"Растёт",
      judging:"Выбрать победителя",
      finished:"Завершена",
      cancelled:"Отменена"
    };
    return m[s]||s;
  }

  function actionName(k){
    return {
      water:"💧 Вода",
      nutrient:"🧪 Питательный раствор",
      shade:"🌘 Закрыть от света"
    }[k]||k;
  }

  function dateText(value){
    if(!value)return "не задана";
    var parts=String(value).split("-");
    if(parts.length!==3)return String(value);
    return parts[2]+"."+parts[1]+"."+parts[0];
  }

  function periodText(b){
    if(!b.start_date&&!b.end_date)return "Даты не заданы";
    return "📅 "+dateText(b.start_date)+" — "+dateText(b.end_date);
  }

  async function loadOptions(){
    var d=await api("/api/v1/admin/battles/options");
    rack.innerHTML=d.racks.map(function(r){
      return '<option value="'+esc(r.device_id)+'|'+r.rack_id+'" '+(r.available?"":"disabled")+'>'+
        esc(r.device_name)+" · полка "+r.rack_id+(r.available?"":" · занята")+
        '</option>';
    }).join("");
    plant.innerHTML=d.plants.map(function(p){
      return '<option value="'+esc(p.id)+'">'+esc(p.name)+'</option>';
    }).join("");
  }

  function entryHtml(b,e){
    var current=e.status==="active"||e.status==="finished";
    var winner=b.status==="judging"&&current
      ? '<button class="battle-winner primary" data-battle="'+esc(b.id)+'" data-entry="'+esc(e.id)+'">🏆 Победитель</button>'
      : (e.is_winner?"🏆 Лучший садовод":"");
    var archived=e.status==="refunded"?" · Возврат Kisa":e.status==="cancelled"?" · Отменено":"";
    var name=e.user_name||"Пользователь";
    var icon=e.user_avatar_url
      ? '<img class="battle-participant-avatar" src="'+esc(e.user_avatar_url)+'" alt="" loading="lazy" decoding="async">'
      : '<span class="battle-participant-avatar battle-participant-placeholder" aria-hidden="true">👤</span>';
    var email=e.user_email
      ? '<span class="battle-participant-email" title="'+esc(e.user_email)+'">'+esc(e.user_email)+'</span>'
      : '<span class="battle-participant-empty">Почта не указана</span>';
    var username=String(e.telegram_username||"").replace(/^@/,"");
    var tg=e.telegram_chat_id||null;
    var telegram=username&&/^[A-Za-z0-9_]{5,32}$/.test(username)
      ? '<a class="battle-participant-telegram" target="_blank" rel="noopener noreferrer" href="https://t.me/'+esc(username)+'">@'+esc(username)+'</a>'
      : tg ? '<span class="battle-participant-telegram">Telegram ID: '+esc(tg)+'</span>'
      : '<span class="battle-participant-empty">Telegram не привязан</span>';
    var videoSection="";
    if(current){
      var ready=!!e.final_video_ready;
      var uploadAllowed=["planting","growing","judging"].includes(b.status);
      var base="/api/v1/admin/battles/"+encodeURIComponent(b.id)+
        "/entries/"+encodeURIComponent(e.id)+"/final-video";
      videoSection='<div class="battle-final-video">'+
        '<span class="battle-final-status '+(ready?"ready":"missing")+'">'+
        (ready?"✓ Итоговое видео загружено":"○ Итоговое видео отсутствует")+'</span>'+
        (ready?'<a href="'+base+'" target="_blank" rel="noopener">▶ Смотреть</a>':"")+
        (uploadAllowed?
          '<label class="battle-final-upload">📹 '+(ready?"Заменить":"Загрузить MP4")+
          '<input type="file" class="battle-final-video-file" data-battle="'+esc(b.id)+
          '" data-entry="'+esc(e.id)+'" accept=".mp4,video/mp4" hidden></label>'+
          (ready?'<button type="button" class="battle-final-delete" data-battle="'+esc(b.id)+
          '" data-entry="'+esc(e.id)+'">Удалить</button>':"")
        :"")+
        '</div>';
    }
    return '<div class="battle-admin-entry'+(current?'':' battle-admin-entry-refunded')+'">'+
      '<div class="battle-participant">'+
        '<span class="battle-participant-slot">#'+esc(e.slot_number)+esc(archived)+'</span>'+icon+
        '<div class="battle-participant-details">'+
          '<span class="battle-participant-name">'+esc(name)+'</span>'+
          email+telegram+
        '</div>'+
      '</div>'+
      '<div class="battle-participant-resources">'+
        '<span>Ⓚ '+esc(e.price_kisa)+'</span>'+
        '<span>💧 '+esc(e.water_used_ml)+'/'+esc(b.water_budget_ml)+' мл</span>'+
        '<span>🧪 '+esc(e.nutrient_used_ml)+'/'+esc(b.nutrient_budget_ml)+' мл</span>'+
        '<span>🌘 '+esc(e.shade_used_minutes)+'/'+esc(b.shade_budget_minutes)+' мин</span>'+
        winner+
      '</div>'+
      videoSection+
      '</div>';
  }

  function battleRow(b){
    var buttons=[
      '<button class="battle-edit" data-id="'+b.id+'">✏️ Изменить</button>'
    ];
    if(b.status==="ready_to_plant"){
      buttons.push('<button class="battle-start primary" data-id="'+b.id+'">🌱 Посадить 6 растений</button>');
    }
    if(b.status==="open"||b.status==="ready_to_plant"){
      buttons.push('<button class="battle-cancel danger" data-id="'+b.id+'">Отменить</button>');
    }
    return '<tr>'+
      '<td><div class="user-name">'+esc(b.title)+'</div>'+
      '<div class="username">'+esc(b.plant_name)+'</div>'+
      '<div class="username">'+esc(periodText(b))+'</div></td>'+
      '<td>'+esc(b.device_id)+'<div class="username">Полка '+b.rack_id+'</div></td>'+
      '<td><span class="badge">'+esc(status(b.status))+'</span><div class="username">'+b.entries_count+'/6</div></td>'+
      '<td>Ⓚ '+b.entry_price_kisa+'<div class="username">Приз: Ⓚ '+b.winner_reward_kisa+'</div></td>'+
      '<td><div class="battle-admin-entries">'+b.entries.map(function(e){return entryHtml(b,e)}).join("")+'</div></td>'+
      '<td><div class="table-actions">'+buttons.join("")+'</div></td>'+
      '</tr>';
  }

  function actionRows(rows){
    var out=[];
    rows.forEach(function(b){
      b.entries.forEach(function(e){
        (e.actions||[]).forEach(function(a){
          if(a.status!=="pending")return;
          out.push(
            '<tr>'+
              '<td>Полка '+b.rack_id+' · контейнер '+e.slot_number+
                '<div class="username">'+esc(e.user_name||"Пользователь")+'</div></td>'+
              '<td>'+actionName(a.kind)+'</td>'+
              '<td>'+a.amount+(a.kind==="shade"?" мин":" мл")+'</td>'+
              '<td>'+esc(fmtDate(a.requested_at))+'</td>'+
              '<td><div class="table-actions">'+
                '<button class="battle-action-complete primary" data-id="'+a.id+'">Выполнено</button>'+
                '<button class="battle-action-reject danger" data-id="'+a.id+'">Отклонить</button>'+
              '</div></td>'+
            '</tr>'
          );
        });
      });
    });
    return out.join("");
  }

  async function loadBattles(){
    try{
      var rows=await api("/api/v1/admin/battles");
      battleRows={};
      rows.forEach(function(b){battleRows[b.id]=b;});
      updateMessageBattles();
      body.innerHTML=rows.length
        ? rows.map(battleRow).join("")
        : '<tr><td colspan="6" class="muted">Битв пока нет.</td></tr>';
      var ar=actionRows(rows);
      actions.innerHTML=ar||'<tr><td colspan="5" class="muted">Нет ожидающих действий.</td></tr>';
    }catch(e){
      toast("Ошибка: "+e.message);
    }
  }

  window.loadBattles=loadBattles;

  var messageBattle=document.getElementById("battleMessageBattle");
  var messageAll=document.getElementById("battleMessageAll");
  var messageRecipients=document.getElementById("battleMessageRecipients");
  var messageHistory=document.getElementById("battleMessageHistory");
  var messageForm=document.getElementById("battleMessageForm");

  function selectedMessageBattle(){
    return battleRows[messageBattle.value]||null;
  }
  function updateMessageRecipients(){
    var battle=selectedMessageBattle();
    var entries=battle?(battle.entries||[]).filter(e=>["active","finished"].includes(e.status)):[];
    messageRecipients.innerHTML=entries.length?entries.map(function(e){
      return '<label class="battle-message-check"><input type="checkbox" value="'+esc(e.id)+
        '" class="battle-message-recipient" '+(messageAll.checked?'checked disabled':'')+'>'+
        ' #'+esc(e.slot_number)+' · '+esc(e.user_name||"Участник")+'</label>';
    }).join(""):'<span class="muted">Нет участников.</span>';
  }
  async function loadMessageHistory(){
    var battle=selectedMessageBattle();
    if(!battle){messageHistory.textContent="Выберите битву.";return;}
    var id=battle.id;
    try{
      var rows=await api("/api/v1/admin/battles/"+id+"/messages");
      if(id!==messageBattle.value)return;
      messageHistory.innerHTML=rows.length?rows.map(function(m){
        var statuses=m.recipients.map(function(r){
          var telegram=r.telegram_status?" · Telegram: "+r.telegram_status:"";
          var push=r.push_status&&r.push_status.length?" · Push: "+r.push_status.join(", "):"";
          return '#'+esc(r.slot_number)+(r.read_at?' · прочитано':' · не прочитано')+esc(telegram+push);
        });
        return '<article class="battle-message-log"><div class="username">'+esc(fmtDate(m.created_at))+
        ' · '+m.recipients.length+' получателей</div><div class="battle-message-text">'+
        esc(m.body)+'</div><small>'+statuses.join(' · ')+'</small></article>';
      }).join(""):'<span class="muted">Сообщений пока нет.</span>';
    }catch(err){messageHistory.textContent="Не удалось загрузить историю: "+err.message;}
  }
  function updateMessageBattles(){
    var previous=messageBattle.value;
    var battles=Object.values(battleRows).filter(b=>b.status!=="cancelled");
    messageBattle.innerHTML=battles.map(function(b){
      return '<option value="'+esc(b.id)+'">'+esc(b.title)+' · полка '+esc(b.rack_id)+'</option>';
    }).join("");
    if(battleRows[previous])messageBattle.value=previous;
    updateMessageRecipients();
    loadMessageHistory();
  }
  messageBattle.addEventListener("change",function(){updateMessageRecipients();loadMessageHistory();});
  messageAll.addEventListener("change",updateMessageRecipients);
  messageForm.addEventListener("submit",async function(event){
    event.preventDefault();
    var battle=selectedMessageBattle();
    if(!battle)return;
    var body=document.getElementById("battleMessageText").value.trim();
    if(!body)return;
    var recipients=messageAll.checked?null:[...messageRecipients.querySelectorAll(".battle-message-recipient:checked")]
      .map(x=>x.value);
    if(recipients!==null&&!recipients.length){toast("Выберите получателей.");return;}
    var count=recipients===null
      ?battle.entries.filter(e=>["active","finished"].includes(e.status)).length
      :recipients.length;
    if(!count){toast("У выбранной битвы нет участников.");return;}
    if(!confirm("Отправить сообщение "+count+" участникам?"))return;
    var btn=document.getElementById("battleMessageSend");
    btn.disabled=true;
    try{
      var sent=await api("/api/v1/admin/battles/"+battle.id+"/messages",{
        method:"POST",body:JSON.stringify({body:body,recipient_entry_ids:recipients})
      });
      toast("Сообщение сохранено для "+sent.recipients+" участников; Telegram в очереди: "+sent.telegram_queued);
      document.getElementById("battleMessageText").value="";
      await loadMessageHistory();
    }catch(err){toast("Ошибка отправки: "+err.message);}
    finally{btn.disabled=false;}
  });


  document.getElementById("section-battles").addEventListener("change",async function(ev){
    var input=ev.target.closest(".battle-final-video-file");
    if(!input || !input.files || !input.files.length)return;
    var file=input.files[0];
    if(file.size>45*1024*1024){
      toast("Видео не должно превышать 45 МБ, иначе Telegram не сможет его отправить.");
      input.value="";
      return;
    }
    var box=input.closest(".battle-final-video");
    var status=box.querySelector(".battle-final-status");
    if(status)status.textContent="⏳ Загружаем "+file.name+"…";
    input.disabled=true;
    try{
      var data=new FormData();
      data.append("video",file,file.name);
      await api("/api/v1/admin/battles/"+encodeURIComponent(input.dataset.battle)+
        "/entries/"+encodeURIComponent(input.dataset.entry)+"/final-video",{
          method:"POST",body:data,
        });
      toast("Итоговое видео загружено. После выбора победителя оно будет отправлено участнику в Telegram.");
      await loadBattles();
    }catch(err){
      toast("Ошибка видео: "+err.message);
      if(status)status.textContent="Не удалось загрузить видео";
      input.disabled=false;
    }
  });

  form.addEventListener("submit",async function(ev){
    ev.preventDefault();
    var parts=rack.value.split("|");
    var startDate=document.getElementById("battleStartDate").value||null;
    var endDate=document.getElementById("battleEndDate").value||null;
    if(startDate&&endDate&&endDate<startDate){
      toast("Дата окончания не может быть раньше даты начала.");
      return;
    }
    var payload={
      device_id:parts[0],
      rack_id:Number(parts[1]),
      plant_id:plant.value,
      title:document.getElementById("battleTitle").value.trim(),
      start_date:startDate,
      end_date:endDate,
      entry_price_kisa:Number(document.getElementById("battlePrice").value),
      water_budget_ml:Number(document.getElementById("battleWater").value),
      nutrient_budget_ml:Number(document.getElementById("battleNutrient").value),
      shade_budget_minutes:Number(document.getElementById("battleShade").value),
      winner_reward_kisa:Number(document.getElementById("battleReward").value)
    };
    try{
      await api("/api/v1/admin/battles",{method:"POST",body:JSON.stringify(payload)});
      toast("Битва создана. Полка исключена из обычной аренды.");
      await loadOptions();
      await loadBattles();
    }catch(e){
      toast("Ошибка: "+e.message);
    }
  });

  editForm.addEventListener("submit",async function(ev){
    ev.preventDefault();
    var id=document.getElementById("battleEditId").value;
    var startDate=document.getElementById("battleEditStartDate").value||null;
    var endDate=document.getElementById("battleEditEndDate").value||null;
    if(startDate&&endDate&&endDate<startDate){
      toast("Дата окончания не может быть раньше даты начала.");
      return;
    }
    var payload={
      title:document.getElementById("battleEditTitle").value.trim(),
      start_date:startDate,
      end_date:endDate,
      water_budget_ml:Number(document.getElementById("battleEditWater").value),
      nutrient_budget_ml:Number(document.getElementById("battleEditNutrient").value),
      shade_budget_minutes:Number(document.getElementById("battleEditShade").value)
    };
    if(payload.title.length<2){
      toast("Название должно содержать минимум 2 символа.");
      return;
    }
    try{
      await api("/api/v1/admin/battles/"+id,{method:"PATCH",body:JSON.stringify(payload)});
      editDialog.close();
      toast("Название, даты и лимиты ресурсов сохранены.");
      await loadBattles();
    }catch(e){
      toast("Ошибка: "+e.message);
    }
  });

  document.getElementById("reloadBattles").addEventListener("click",function(){
    loadOptions();
    loadBattles();
  });

  document.getElementById("section-battles").addEventListener("click",async function(ev){
    var b=ev.target.closest(".battle-edit");
    if(b){
      var item=battleRows[b.dataset.id];
      if(!item)return;
      document.getElementById("battleEditId").value=item.id;
      document.getElementById("battleEditTitle").value=item.title||"";
      document.getElementById("battleEditStartDate").value=item.start_date||"";
      document.getElementById("battleEditEndDate").value=item.end_date||"";
      document.getElementById("battleEditWater").value=item.water_budget_ml;
      document.getElementById("battleEditNutrient").value=item.nutrient_budget_ml;
      document.getElementById("battleEditShade").value=item.shade_budget_minutes;
      editDialog.showModal();
      return;
    }

    b=ev.target.closest(".battle-start");
    if(b){
      if(!confirm("Все 6 растений физически готовы к посадке? Поставить команды Raspberry?"))return;
      b.disabled=true;
      try{
        await api("/api/v1/admin/battles/"+b.dataset.id+"/start",{method:"POST"});
        toast("Команды посадки поставлены в очередь.");
        await loadBattles();
      }catch(e){
        b.disabled=false;
        toast("Ошибка: "+e.message);
      }
      return;
    }

    b=ev.target.closest(".battle-cancel");
    if(b){
      if(!confirm("Отменить битву и вернуть участникам Kisa?"))return;
      try{
        await api("/api/v1/admin/battles/"+b.dataset.id+"/cancel",{method:"POST"});
        toast("Битва отменена, Kisa возвращены.");
        await loadOptions();
        await loadBattles();
      }catch(e){
        toast("Ошибка: "+e.message);
      }
      return;
    }

    b=ev.target.closest(".battle-final-delete");
    if(b){
      if(!confirm("Удалить итоговое видео этого контейнера?"))return;
      b.disabled=true;
      try{
        await api("/api/v1/admin/battles/"+encodeURIComponent(b.dataset.battle)+
          "/entries/"+encodeURIComponent(b.dataset.entry)+"/final-video",{method:"DELETE"});
        toast("Итоговое видео удалено.");
        await loadBattles();
      }catch(e){toast("Ошибка: "+e.message);b.disabled=false;}
      return;
    }

    b=ev.target.closest(".battle-winner");
    if(b){
      var battle=battleRows[b.dataset.battle];
      var missing=battle?battle.entries.filter(e=>["active","finished"].includes(e.status)&&!e.final_video_ready).length:0;
      var note="Назначить этот контейнер победителем? Будет начислен приз и разосланы итоговые видео участникам с привязанным Telegram.";
      if(missing)note+="\nВнимание: для "+missing+" контейнеров итоговое видео не загружено. Их участники получат только диплом.";
      if(!confirm(note))return;
      try{
        await api("/api/v1/admin/battles/"+b.dataset.battle+"/winner",{
          method:"POST",
          body:JSON.stringify({entry_id:b.dataset.entry})
        });
        toast("Победитель выбран.");
        await loadBattles();
      }catch(e){
        toast("Ошибка: "+e.message);
      }
      return;
    }

    b=ev.target.closest(".battle-action-complete");
    if(b){
      try{
        await api("/api/v1/admin/battles/actions/"+b.dataset.id+"/complete",{method:"POST"});
        toast("Действие отмечено выполненным.");
        await loadBattles();
      }catch(e){
        toast("Ошибка: "+e.message);
      }
      return;
    }

    b=ev.target.closest(".battle-action-reject");
    if(b){
      var note=prompt("Причина отклонения:","");
      if(note===null)return;
      try{
        await api("/api/v1/admin/battles/actions/"+b.dataset.id+"/reject",{
          method:"POST",
          body:JSON.stringify({note:note})
        });
        toast("Действие отклонено, ресурс возвращён участнику.");
        await loadBattles();
      }catch(e){
        toast("Ошибка: "+e.message);
      }
    }
  });
})();
