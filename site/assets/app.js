/* Oregon Tow & Recovery Tracker — static client, no tracking or analytics. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const state = { records:[], demo:false, tab:'all', limit:30, map:null, mapsRequested:false };
  const label = {
    stolen_recovery:'Stolen recovery', needs_review:'Review needed', impound:'Impound',
    parking:'Parking / construction', private_property:'Private property impound', abandoned:'Abandoned', collision:'Collision',
    traffic:'Traffic / hazard', other:'Other'
  };
  const agencyLabel = {PPB:'Portland Police',MCSO:'Multnomah Sheriff',TRIMET:'TriMet / Transit Police',PORT_POLICE:'Port of Portland Police',PBOT:'PBOT',OTHER:'Other / unknown'};
  const html = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm = value => String(value ?? '').toUpperCase().replace(/[^A-Z0-9]/g,'');
  const vinLastFour = record => {
    const known = norm(record.vin_last4);
    if (/^[A-Z0-9]{4}$/.test(known)) return known;
    const full = norm(record.vin);
    return /^[A-HJ-NPR-Z0-9]{17}$/.test(full) ? full.slice(-4) : '';
  };
  const maskedVin = record => vinLastFour(record) ? '••••' + vinLastFour(record) : 'Not available';
  const parsedDate = record => new Date(record.towed_at || record.towed_at_raw || 0);
  const showDate = rec => {
    const d = parsedDate(rec);
    return !Number.isNaN(+d) && +d > 0
      ? d.toLocaleString('en-US',{timeZone:'America/Los_Angeles',year:'numeric',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}) + ' PT'
      : rec.towed_at_raw || 'Date unavailable';
  };
  const mapsLink = value => 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(value);
  const mapAnchor = value => value ? `<a href="${html(mapsLink(value))}" target="_blank" rel="noopener noreferrer">Google Maps ↗</a>` : '<span class="muted">Location not supplied</span>';
  const safeURL = value => {try {const url=new URL(value);return url.protocol === 'https:' && url.hostname === 'search.autoreturn.com' && url.pathname === '/find-vehicle/details' ? url.href : '';} catch{return '';}};
  function vehicleKey(r) {
    // A full VIN is a stronger identifier. Plate+state+model is only a possible match.
    if (/^[A-HJ-NPR-Z0-9]{17}$/.test(norm(r.vin))) return 'vin:' + norm(r.vin);
    const plate = norm(r.license_plate), region = norm(r.license_state);
    const model = norm(String(r.vehicle||'').replace(/\b(?:WHITE|BLACK|SILVER|GRAY|GREY|BLUE|RED|GREEN|BROWN|GOLD|BEIGE|TAN|YELLOW)\b/ig,''));
    return plate && region && model ? 'possible:' + plate + ':' + region + ':' + model : 'unique:' + r.id;
  }
  function vehicleHistory(r) {
    const key = vehicleKey(r);
    // When one record has full VIN and another only a masked VIN, do not silently join.
    return state.records.filter(x => {
      if (vehicleKey(x) !== key) return false;
      // Two different visible VIN suffixes must never be treated as one vehicle.
      return !(r.vin_last4 && x.vin_last4 && norm(r.vin_last4) !== norm(x.vin_last4));
    }).sort((a,b)=>+parsedDate(b)-+parsedDate(a));
  }
  function activeRecords() {
    const search = $('q').value.trim(), q = norm(search);
    const from = $('from').value, to = $('to').value;
    const reason = state.tab === 'stolen' ? 'stolen_recovery' : $('reason').value;
    return state.records.filter(r => {
      if (reason !== 'all' && r.reason_category !== reason) return false;
      if ($('agency').value !== 'all' && r.agency !== $('agency').value) return false;
      const date = (r.towed_at||'').slice(0,10);
      if (from && (!date || date < from)) return false;
      if (to && (!date || date > to)) return false;
      if (!q) return true;
      const searchFields = [r.license_plate, r.license_state, r.vehicle, r.towed_by, r.reason_raw, r.tr_number, r.id].map(norm);
      if (searchFields.some(s => s.includes(q))) return true;
      // A full VIN is only a POSSIBLE suffix match if source reveals last four.
      if (r.vin && norm(r.vin).includes(q)) return true;
      if (r.vin_last4 && q.length >= 4 && (q === norm(r.vin_last4) || q.slice(-4) === norm(r.vin_last4))) return true;
      return false;
    }).sort((a,b)=> $('sort').value === 'oldest' ? +parsedDate(a)-+parsedDate(b) : +parsedDate(b)-+parsedDate(a));
  }
  function pill(r) { return `<span class="pill ${html(r.reason_category || 'other')}">${html(label[r.reason_category] || 'Other')}</span>`; }
  function card(r) {
    const plate = [r.license_plate,r.license_state].filter(Boolean).join(' · ') || 'Unknown plate';
    return `<article class="record"><div>
      <div class="record-title">${html(r.vehicle || 'Unknown vehicle')}<small>${html(plate)} · VIN ${html(maskedVin(r))} · AutoReturn #${html(r.id)}</small></div>
      <div class="record-meta"><span>◷ ${html(showDate(r))}</span><span>◆ ${html(agencyLabel[r.agency] || r.towed_by || 'Unknown agency')}</span><span>● ${html(r.status || 'Unknown status')}</span></div>
      </div><div class="record-actions">${pill(r)}<button data-history="${html(r.id)}">View tow history →</button></div>
      <div class="record-data"><div><strong>Reason listed</strong>${html(r.reason_raw || 'Not provided')}</div><div><strong>Towed from</strong>${html(r.towed_from || 'Not provided')}</div><div><strong>Tow company / yard</strong>${html(r.tow_company || 'Not provided')}</div></div></article>`;
  }
  function render() {
    const records = activeRecords();
    $('countAll').textContent = state.records.length.toLocaleString();
    $('countStolen').textContent = state.records.filter(r=>r.reason_category==='stolen_recovery').length.toLocaleString();
    $('countMatches').textContent = records.length.toLocaleString();
    $('resultTitle').textContent = state.tab === 'stolen' ? 'Recorded stolen-vehicle recoveries' : 'Recent tow records';
    $('resultDescription').textContent = `${records.length.toLocaleString()} matching records · ${$('sort').value === 'oldest' ? 'oldest first' : 'newest first'}`;
    for (const b of document.querySelectorAll('[data-tab]')) b.classList.toggle('active',b.dataset.tab===state.tab);
    $('resultsView').hidden = state.tab === 'map';
    $('mapView').hidden = state.tab !== 'map';
    if (state.tab === 'map') { showMap(records); return; }
    $('records').innerHTML = records.length ? records.slice(0,state.limit).map(card).join('') : '<div class="empty">No tow records match these filters. Try another plate, VIN suffix, or date range.</div>';
    $('more').hidden = records.length <= state.limit;
    $('more').textContent = `Load more (${Math.min(records.length-state.limit,30)} next)`;
  }
  function feeMarkup(record) {
    const fees = Array.isArray(record.fee_details) ? record.fee_details : [];
    if (!fees.length) return '';
    return `<p class="fine">Fee details listed at time of collection (may change): ${fees.map(f => `${html(f.label)}: ${html(f.amount)}`).join(' · ')}</p>`;
  }
  function showHistory(id) {
    const r = state.records.find(x=>String(x.id)===String(id));
    if (!r) return;
    const history = vehicleHistory(r);
    const possible = vehicleKey(r).startsWith('possible:');
    const title = r.vehicle || 'Vehicle record';
    const plate = [r.license_plate, r.license_state].filter(Boolean).join(' · ') || 'Unknown plate';
    $('detailContent').innerHTML = `<h2 id="detailTitle" class="detail-title">${html(title)}</h2>
      <p class="detail-subtitle">License ${html(plate)} · VIN ${html(maskedVin(r))}</p>
      ${possible ? '<p class="notice demo">Possible history match: grouped by plate, state, and vehicle description. Plates can be reassigned; the source masks VINs. This does not confirm a single vehicle identity.</p>' : ''}
      <div class="detail-stats"><div><strong>${history.length}</strong><span>Matching tow records</span></div><div><strong>${history.filter(x=>x.reason_category==='stolen_recovery').length}</strong><span>Stolen recoveries listed</span></div><div><strong>${html(r.license_state||'—')}</strong><span>Plate state</span></div></div>
      <h3>Recorded tow timeline</h3><div class="timeline">${history.map(x=>`
      <div class="timeline-item"><strong>${html(showDate(x))}</strong> ${pill(x)}<p>${html(x.reason_raw||'Unspecified reason')} · ${html(x.status||'Unknown status')}</p>
        ${vinLastFour(x) ? `<p class="fine">VIN ${html(maskedVin(x))}</p>` : ''}
        <p>Picked up: ${html(x.towed_from||'Location unavailable')} · ${mapAnchor(x.towed_from)}</p>
        <p>Agency: ${html(agencyLabel[x.agency]||x.towed_by||'Unknown')} · Storage: ${html(x.tow_company||'Unknown')}</p>
        ${x.tow_company_address?`<p>Storage yard: ${html(x.tow_company_address)}</p>`:''}
        ${feeMarkup(x)}
        <p>Record #${html(x.id)} ${safeURL(x.source_url)?`· <a href="${html(safeURL(x.source_url))}" target="_blank" rel="noopener noreferrer">Original AutoReturn record ↗</a>`:''}</p>
        ${(x.status_history||[]).length>1?`<p class="fine">Observed status changes: ${html(x.status_history.map(s=>s.status).join(' → '))}</p>`:''}
      </div>`).join('')}</div><p class="fine">Only history actually present in this archive is shown; absence does not mean the vehicle was never previously towed.</p>`;
    $('detailModal').hidden = false;
    document.body.style.overflow = 'hidden';
    $('closeDetail').focus();
  }
  function closeHistory(){ $('detailModal').hidden=true; document.body.style.overflow=''; }
  function fallbackMap(records, message) {
    $('map').innerHTML = `<div class="map-message"><div style="font-size:40px">⌖</div><strong>Google Maps integration</strong><p>${html(message)}</p></div>`;
    const locations = records.filter(r=>r.towed_from).slice(0,100);
    $('mapFallback').innerHTML = locations.length ? `<strong>Open tow pickup locations in Google Maps</strong>${locations.map(r=>`<div class="map-link-row">${html(r.vehicle)} · ${html(showDate(r))} · ${mapAnchor(r.towed_from)}</div>`).join('')}` : 'No tow pickup locations available for this selection.';
  }
  function googleReady(records) {
    const mapEl = $('map');
    mapEl.innerHTML = '';
    const map = new google.maps.Map(mapEl,{center:{lat:44.5,lng:-122.8},zoom:7,mapTypeControl:false,streetViewControl:false});
    state.map=map;
    const bounds = new google.maps.LatLngBounds();
    let pinCount=0;
    // Coordinates are preferred. For a small demo geocode no more than 25 text addresses.
    const geocoder=new google.maps.Geocoder();
    const addressRecords=[];
    for(const r of records.slice(0,100)){
      if(Number.isFinite(Number(r.lat)) && Number.isFinite(Number(r.lng)) && r.lat !== null && r.lng !== null){
        addPin({lat:Number(r.lat),lng:Number(r.lng)},r);continue;
      }
      if(r.towed_from) addressRecords.push(r);
    }
    function addPin(position,r){
      const marker=new google.maps.Marker({position,map,title:`${r.vehicle} — ${r.towed_from}`});
      const info=new google.maps.InfoWindow({content:`<strong>${html(r.vehicle)}</strong><p>${html(showDate(r))}</p><p>${html(r.reason_raw)}</p><p>${html(r.towed_from)}</p>`});
      marker.addListener('click',()=>info.open({anchor:marker,map}));bounds.extend(position);pinCount++;if(pinCount>1)map.fitBounds(bounds);else map.setCenter(position);
    }
    // Geocode conservatively to avoid quota spikes; do not infer stolen location from the yard.
    addressRecords.slice(0,25).forEach((r,i)=>{
      window.setTimeout(()=>geocoder.geocode({address:r.towed_from},(results,status)=>{
        if(state.tab !== 'map')return;
        if(status==='OK'&&results?.[0])addPin(results[0].geometry.location,r);
      }),i*350);
    });
    $('mapFallback').textContent = `Mapping up to ${Math.min(records.length,100)} records; addresses are limited to 25 per view unless pre-geocoded. Exact pickup addresses may be approximate or incomplete.`;
  }
  function showMap(records) {
    const key = (window.TOW_TRACKER_CONFIG||{}).googleMapsApiKey || '';
    if(!key) return fallbackMap(records,'Add a referrer-restricted Google Maps JavaScript API key in config.js to enable interactive pins. Until then, the links below work without an API key.');
    if(window.google?.maps) return googleReady(records);
    if(state.mapsRequested)return;
    state.mapsRequested=true;
    fallbackMap(records,'Loading Google Maps…');
    const script=document.createElement('script');
    script.src='https://maps.googleapis.com/maps/api/js?key='+encodeURIComponent(key);
    script.async=true;
    script.onload=()=>googleReady(activeRecords());
    script.onerror=()=>{state.mapsRequested=false;fallbackMap(activeRecords(),'Google Maps could not load. Check your API key and allowed referrers.');};
    document.head.appendChild(script);
  }
  function bind() {
    ['q','reason','agency','from','to','sort'].forEach(id=>$(id).addEventListener(id==='q'?'input':'change',()=>{state.limit=30;render();}));
    $('clear').addEventListener('click',()=>{['q','from','to'].forEach(id=>$(id).value='');['reason','agency','sort'].forEach(id=>$(id).selectedIndex=0);state.limit=30;render();});
    $('more').addEventListener('click',()=>{state.limit+=30;render();});
    document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{state.tab=b.dataset.tab;state.limit=30;render();}));
    $('records').addEventListener('click',e=>{const b=e.target.closest('[data-history]');if(b)showHistory(b.dataset.history);});
    $('closeDetail').addEventListener('click',closeHistory);
    $('detailModal').addEventListener('click',e=>{if(e.target.dataset.close)closeHistory();});
    window.addEventListener('keydown',e=>{if(e.key==='Escape')closeHistory();});
  }
  async function initialize() {
    bind();
    try {
      const res=await fetch('data/records.json',{cache:'no-store'});
      if(!res.ok)throw new Error(`Data HTTP ${res.status}`);
      const data=await res.json();
      state.records=Array.isArray(data.records) ? data.records.filter(r=>r.geo_scope==='include') : [];
      if(!state.records.length){
        const sample=await fetch('data/demo.json').then(r=>r.json());
        state.records=sample.records;state.demo=true;
        $('notice').classList.add('demo');
        $('notice').textContent='DEMONSTRATION ONLY — all displayed vehicles and towing events are fictional. No live archive records have been published yet.';
      } else {
        $('notice').textContent='Archive records only. “Stolen recovery” means the original tow reason explicitly used stolen-related wording; no independent theft verification is implied.';
      }
      $('updated').textContent = data.generated_at ? 'Archive built ' + new Date(data.generated_at).toLocaleDateString('en-US') + '.' : '';
    } catch(error) {
      state.records=[];
      $('notice').textContent='Could not load the archive: ' + error.message + '. Run the site from a local HTTP server or GitHub Pages.';
    }
    render();
  }
  initialize();
})();
