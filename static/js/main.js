
window.addEventListener('DOMContentLoaded', ()=>{
// 🪟 Chat → Fullscreen result (macOS-style)
const sendBtn = document.querySelector('.chat-box button');
const inputEl = document.querySelector('.chat-box textarea');
const overlay = document.getElementById('resultOverlay');
const resultBody = document.getElementById('resultBody');
const closeBtn = document.getElementById('closeResult');
const minBtn = document.getElementById('minResult');
const chip = document.getElementById('resultChip');

// 🧠 realistic AI thinking
function typeWriterAdvanced(el, text){
  el.innerHTML = '';

  const cursor = document.createElement('span');
  cursor.innerHTML = '|';
  cursor.style.animation = 'blink 1s infinite';

  // ⏳ thinking phase
  el.innerHTML = 'Analyzing data...';

  setTimeout(()=>{
    el.innerHTML = '';
    el.appendChild(cursor);

    let i = 0;

    function type(){
      if(i < text.length){
        const char = text.charAt(i);
        cursor.insertAdjacentText('beforebegin', char);

       if(char === '\n'){
  setTimeout(type, 120);
} else {
  setTimeout(type, 18);
}

        i++;
      } else {
        cursor.remove();
      }
    }

    type();

  }, 1000);
}

function openResult(text){
  overlay.classList.add('open');
  chip.classList.remove('show');
  typeWriterAdvanced(resultBody, text);
}

function closeResult(){
  overlay.classList.remove('open');
}

function minimizeResult(){
  overlay.classList.remove('open');
  chip.classList.add('show');
}

sendBtn.addEventListener('click', ()=>{
  const val = inputEl.value.trim();
  if(!val) return;

  openResult(`Result for: ${val}

• Insight A detected
• Pattern emerging in data
• Recommendation: Adjust strategy`);

  inputEl.value='';
});

closeBtn.addEventListener('click', closeResult);
minBtn.addEventListener('click', minimizeResult);
chip.addEventListener('click', ()=> overlay.classList.add('open'));
});


// 📈 Sales chart
new Chart(document.getElementById('chart'), {
  type:'line',
  data:{ labels:['Jan','Feb','Mar','Apr'], datasets:[{ data:[12,19,30,25], borderColor:'#7c3aed', tension:0.3 }] },
  options:{
    responsive:true,
    maintainAspectRatio:false,
    animation:false,
    plugins:{ legend:{display:false} },
    scales:{
      x:{ grid:{display:false} },
      y:{ grid:{color:'rgba(0,0,0,0.05)'} }
    }
  }
});

// 🕯️ Profit/Loss Candlestick
const candleData = [
  {o:4,h:6,l:3,c:5},
  {o:-1,h:1,l:-3,c:-2},
  {o:5,h:9,l:4,c:8},
  {o:3,h:6,l:2,c:4}
];

const candlePlugin = {
  id:'candles',
  afterDatasetsDraw(chart){
    const {ctx, scales:{x,y}} = chart;
    ctx.save();
    candleData.forEach((d,i)=>{
      const xPos = x.getPixelForValue(i);
      const high = y.getPixelForValue(d.h);
      const low = y.getPixelForValue(d.l);
      ctx.beginPath();
      ctx.moveTo(xPos, high);
      ctx.lineTo(xPos, low);
      ctx.strokeStyle = d.c >= d.o ? '#22c55e' : '#ef4444';
      ctx.stroke();
    });
    ctx.restore();
  }
};

new Chart(document.getElementById('chart2'), {
  type:'bar',
  data:{
    labels:['Jan','Feb','Mar','Apr'],
    datasets:[{
      data:candleData.map(d=>[d.o,d.c]),
      backgroundColor:candleData.map(d=> d.c>=d.o ? '#22c55e':'#ef4444'),
      barThickness:8
    }]
  },
  options:{
    responsive:true,
    maintainAspectRatio:false,
    animation:false,
    layout:{ padding:{bottom:20}},
    plugins:{ legend:{display:false} },
    scales:{
      x:{ grid:{display:false}, ticks:{padding:10}},
      y:{
        grid:{color:'rgba(0,0,0,0.05)'},
        suggestedMin: Math.min(...candleData.map(d=>d.l)) - 1
      }
    }
  },
  plugins:[candlePlugin]
});

// 🎯 tilt + glow + blur + spotlight
const cards = document.querySelectorAll('.card');

const spotlight = document.createElement('div');
spotlight.className = 'spotlight';
document.body.appendChild(spotlight);

cards.forEach(card=>{
  card.addEventListener('mouseenter',()=>{
    document.querySelector('.app').classList.add('focus-mode');
    card.classList.add('active');
  });

  card.addEventListener('mouseleave',()=>{
    document.querySelector('.app').classList.remove('focus-mode');
    card.classList.remove('active');
    card.style.transform='perspective(600px) rotateX(0deg) rotateY(0deg)';
  });

  card.addEventListener('pointermove',e=>{
    const r = card.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;

    card.style.setProperty('--x', x+'px');
    card.style.setProperty('--y', y+'px');

    const rx = (y - r.height/2)/15;
    const ry = (r.width/2 - x)/15;
    card.style.transform = `perspective(600px) rotateX(${rx}deg) rotateY(${ry}deg)`;

    spotlight.style.left = e.clientX - 150 + 'px';
    spotlight.style.top = e.clientY - 150 + 'px';
  });

  // 💧 ripple fill effect on click
  card.addEventListener('click', (e)=>{
    const rect = card.getBoundingClientRect();
    const circle = document.createElement('span');
    const size = Math.max(rect.width, rect.height);

    circle.classList.add('ripple');
    circle.style.width = circle.style.height = size + 'px';
    circle.style.left = (e.clientX - rect.left - size/2) + 'px';
    circle.style.top = (e.clientY - rect.top - size/2) + 'px';

    card.appendChild(circle);

    setTimeout(()=>{
      circle.remove();
    },600);
  });
});


// 🌗 Theme toggle (FIXED)
const themeToggle = document.getElementById('themeToggle');

themeToggle.addEventListener('click', () => {
  document.body.classList.toggle('dark');
  themeToggle.textContent = document.body.classList.contains('dark') ? '☀️' : '🌙';
});

// 📩 Universal popup toggle for sidebar cards
const popupCards = document.querySelectorAll('.popup-card');

popupCards.forEach(card=>{
  const header = card.querySelector('.popup-header');
  const panel = card.querySelector('.popup-panel');
  const badge = card.querySelector('.badge');

  header.addEventListener('click', ()=>{

    // 🎯 accordion close others
    popupCards.forEach(c=>{
      if(c!==card){
        c.querySelector('.popup-panel').style.display='none';
      }
    });

    const isOpen = panel.style.display==='block';
    panel.style.display = isOpen ? 'none' : 'block';

    if(!isOpen && badge){
      badge.style.display='none';
    }
  });
});

// 🧠 Sidebar-driven notification system (no top toasts)
function pingCard(card){
  card.classList.add('notify');
  setTimeout(()=> card.classList.remove('notify'), 1200);
}

// ✨ subtle highlight for updates
const style = document.createElement('style');
style.innerHTML = `
.popup-card.notify{
  box-shadow: 0 0 0 0 rgba(124,58,237,0.4);
  animation: ping 1.2s ease;
}
@keyframes ping{
  0%{ box-shadow:0 0 0 0 rgba(124,58,237,0.5);} 
  70%{ box-shadow:0 0 0 10px rgba(124,58,237,0);} 
  100%{ box-shadow:0 0 0 0 rgba(124,58,237,0);} 
}`;
document.head.appendChild(style);

// 🧠 auto-update badges simulation (updates stay in sidebar)
setInterval(()=>{
  const cards = document.querySelectorAll('.popup-card');

  cards.forEach(card=>{
    const title = card.querySelector('strong').innerText;
    const badge = card.querySelector('.badge');

    let type = 'low';

    if(title.includes('Anomalies')) type = 'high';
    else if(title.includes('Performance')) type = 'medium';

    if(Math.random() > 0.6){
      if(badge){
        badge.style.display='inline-block';
        badge.innerText = parseInt(badge.innerText || 0) + 1;
      }
      pingCard(card);
    }
  });
},6000);

