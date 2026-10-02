import React, { useEffect, useState, useRef } from 'react'
import { createRoot } from 'react-dom/client'
import {
  BookOpen, ChefHat, ExternalLink, LoaderCircle, Plus, Search, ShoppingBasket,
  Sparkles, Trash2, Utensils, X, Check, RefreshCw
} from 'lucide-react'
import './styles.css'
import { copyText } from './clipboard'

const API = import.meta.env.VITE_API_URL || ''

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try { const d = await res.json(); message = d.detail || message } catch {}
    throw new Error(message)
  }
  return res.json()
}

function Toast({ message, onClose }) {
  if (!message) return null
  return <div className="toast"><span>{message}</span><button onClick={onClose}><X size={16}/></button></div>
}

function App() {
  const [tab, setTab] = useState('discover')
  const [categories, setCategories] = useState([])
  const [category, setCategory] = useState('Popular')
  const [discover, setDiscover] = useState([])
  const [discoverPage, setDiscoverPage] = useState(1)
  const [library, setLibrary] = useState([])
  const [search, setSearch] = useState('')
  const [discoverInput, setDiscoverInput] = useState('')
  const [discoverQuery, setDiscoverQuery] = useState('')
  const [discoverRefresh, setDiscoverRefresh] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [discoverError, setDiscoverError] = useState('')
  const [unavailableCount, setUnavailableCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState('')
  const [url, setUrl] = useState('')
  const [selected, setSelected] = useState({})
  const [grocery, setGrocery] = useState([])
  const [listVersion, setListVersion] = useState(0)
  const [listLoading, setListLoading] = useState(false)
  const [toast, setToast] = useState('')
  const [preview, setPreview] = useState(null)
  const previewRequest = useRef(0)
  const busy = useRef(false)
  const applyPlan = recipes => setSelected(Object.fromEntries(recipes.map(r => [r.id, {...r, base_servings: r.servings, servings: r.planned_servings}])))
  const openRecipe = async recipe => {
    if (recipe.base_servings !== undefined) recipe = {...recipe, servings: recipe.base_servings}
    const request = ++previewRequest.current
    setPreview({recipe, loading: !recipe.ingredients})
    if (recipe.ingredients) return
    try {
      const detail = await api('/api/preview', {method: 'POST', body: JSON.stringify({url: recipe.url || recipe.source_url})})
      if (request === previewRequest.current) setPreview({recipe: detail, loading: false})
    } catch (e) {
      if (request === previewRequest.current) setPreview({recipe, error: e.message})
    }
  }
  const closeRecipe = () => { ++previewRequest.current; setPreview(null) }
  const changePlan = async (path, options) => {
    if (busy.current) return
    busy.current = true
    setImporting(path)
    try { applyPlan(await api(path, options)) }
    catch (e) { setToast(e.message) }
    finally { busy.current = false; setImporting('') }
  }
  const addToPlan = recipe => changePlan('/api/meal-plan', {method: 'POST', body: JSON.stringify({url: recipe.url || recipe.source_url})})
  const removeFromPlan = id => changePlan(`/api/meal-plan/${id}`, {method: 'DELETE'})
  const updateServings = (id, value) => {
    if (!Number.isFinite(Number(value)) || Number(value) <= 0) return
    changePlan(`/api/meal-plan/${id}`, {method: 'PATCH', body: JSON.stringify({id, servings: Number(value)})})
  }
  const saved = recipe => library.some(r => r.source_url === (recipe.source_url || recipe.url))
  const planned = recipe => Object.values(selected).some(r => r.source_url === (recipe.source_url || recipe.url))
  const cardProps = recipe => ({recipe, saved: saved(recipe), selected: planned(recipe), busy: !!importing,
    onOpen: () => openRecipe(recipe), onSave: () => importUrl(recipe.source_url || recipe.url), onAdd: () => addToPlan(recipe), onRemove: () => removeFromCookbook(recipe)})


  const loadLibrary = async (q = '') => setLibrary(await api(`/api/recipes?q=${encodeURIComponent(q)}`))
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setDiscover([])
    setDiscoverError('')
    setUnavailableCount(0)
    api(`/api/discover?category=${encodeURIComponent(category)}&page=${discoverPage}&q=${encodeURIComponent(discoverQuery)}`, {signal: controller.signal})
      .then(data => {
        if (controller.signal.aborted) return
        setDiscover(data.items || [])
        setHasMore(data.has_more ?? (data.items?.length > 0))
        setUnavailableCount(data.unavailable_count || 0)
      })
      .catch(e => { if (!controller.signal.aborted) setDiscoverError(e.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [category, discoverPage, discoverQuery, discoverRefresh])

  const clearDiscoverSearch = () => {setDiscoverInput('');setDiscoverQuery('');setDiscoverPage(1)}

  useEffect(() => {
    api('/api/categories').then(setCategories).catch(() => setCategories(['Popular','Quick','One Pot','Chicken','Vegetarian']))
    api('/api/meal-plan').then(applyPlan).catch(e => setToast(e.message))
    loadLibrary().catch(e => setToast(e.message))
  }, [])

  useEffect(() => {
    let active = true
    setGrocery([])
    const recipes = Object.values(selected).map(r => ({id: r.id, servings: Number(r.servings)}))
    setListLoading(!!recipes.length)
    if (recipes.length) api('/api/grocery-list', {method: 'POST', body: JSON.stringify({recipes})})
      .then(data => { if (active) setGrocery(data.items || []) })
      .catch(e => { if (active) setToast(e.message) })
      .finally(() => { if (active) setListLoading(false) })
    return () => { active = false }
  }, [selected, listVersion])

  const importUrl = async (recipeUrl) => {
    if (!recipeUrl || busy.current) return
    busy.current = true
    setImporting(recipeUrl)
    try {
      const recipe = await api('/api/import', { method: 'POST', body: JSON.stringify({ url: recipeUrl }) })
      await loadLibrary()
      setToast(`Saved ${recipe.title}`)
      setUrl('')
    } catch (e) { setToast(e.message) }
    finally { busy.current = false; setImporting('') }
  }

  const removeFromCookbook = async recipe => {
    const entry = library.find(r => r.source_url === (recipe.source_url || recipe.url))
    if (!entry || busy.current) return
    busy.current = true
    setImporting(entry.source_url)
    try {
      await api(`/api/recipes/${entry.id}`, {method: 'DELETE'})
      setLibrary(prev => prev.filter(r => r.id !== entry.id))
      setToast(`Removed ${entry.title} from Cookbook`)
    } catch (e) { setToast(e.message) }
    finally { busy.current = false; setImporting('') }
  }

  const buildList = () => { setListVersion(v => v + 1); setTab('grocery') }

  const selectedCount = Object.keys(selected).length
  return <div className="app-shell">
    <header>
      <button className="brand" aria-label="Pantry Pilot — Discover" onClick={()=>{setTab('discover');setSearch('');clearDiscoverSearch()}}><div className="logo"><ChefHat size={23}/></div><div><strong>Pantry Pilot</strong><span>recipes → groceries</span></div></button>
      <nav>
        <button className={tab==='discover'?'active':''} onClick={()=>setTab('discover')}><Sparkles size={17}/>Discover</button>
        <button className={tab==='library'?'active':''} onClick={()=>setTab('library')}><BookOpen size={17}/>Cookbook <b>{library.length}</b></button>
        <button className={tab==='grocery'?'active':''} onClick={()=>setTab('grocery')}><ShoppingBasket size={17}/>Grocery list {selectedCount>0 && <b>{selectedCount}</b>}</button>
      </nav>
    </header>

    <main>
      <section className="hero">
        <div><div className="eyebrow">LOCAL-FIRST MEAL TOOL</div><h1>What sounds good?</h1><p>Browse Budget Bytes, save what you like, and turn recipes into one clean grocery list.</p></div>
        <div className="stats"><div><b>{library.length}</b><span>saved recipes</span></div><div><b>{selectedCount}</b><span>in your Meal Plan</span></div></div>
      </section>

      {tab !== 'grocery' && <div className="toolbar">
        <form className="search" onSubmit={e=>{e.preventDefault();if(tab==='discover'){setDiscoverQuery(discoverInput.trim());setDiscoverPage(1);setDiscoverRefresh(v=>v+1)}}}><Search size={18}/><input aria-label={tab==='discover'?'Search Budget Bytes recipes':'Search Cookbook'} maxLength={120} value={tab==='discover'?discoverInput:search} onChange={e=>tab==='discover'?setDiscoverInput(e.target.value):setSearch(e.target.value)} placeholder={tab==='discover'?'Search Budget Bytes recipe names…':'Search your saved recipes…'}/>{(tab==='discover'?discoverInput || discoverQuery:search) && <button type="button" aria-label="Clear search" onClick={()=>tab==='discover'?clearDiscoverSearch():setSearch('')}><X size={16}/></button>}{tab==='discover' && <button className="search-submit" type="submit">Search</button>}</form>
        <div className="url-import"><input value={url} onChange={e=>setUrl(e.target.value)} placeholder="Paste a recipe URL…"/><button disabled={!url || importing} onClick={()=>openRecipe({url, title: 'Recipe preview'})}>{importing===url?<LoaderCircle className="spin" size={17}/>:<Plus size={17}/>}Preview</button></div>
      </div>}

      {tab === 'discover' && <>
        <div className="category-row">
          <div className="chips">{categories.map(c => <button key={c} className={category===c?'chip active':'chip'} onClick={()=>{setCategory(c);setDiscoverPage(1);clearDiscoverSearch()}}>{c}</button>)}</div>
          <button className="ghost" onClick={()=>setDiscoverRefresh(v=>v+1)}><RefreshCw size={16}/>Refresh</button>
        </div>
        {discoverQuery && <p className="muted">Budget Bytes recipe results for “{discoverQuery}” — all categories</p>}
        {unavailableCount > 0 && <p role="status" className="muted">Some recipes could not be checked. Refresh to try again.</p>}
        {loading ? <Loading/> : discoverError ? <p role="alert">{discoverError}</p> : !discover.length ? <Empty icon={<Search/>} title="No recipes found on this page" body={hasMore?'Try the next page for more matches.':'Try another recipe name.'}/> : <div className="card-grid">{discover.map((r,i)=><RecipeCard key={`${r.url}-${i}`} {...cardProps(r)}/>)}</div>}
        <div className="pager"><button disabled={loading || discoverPage<=1} onClick={()=>{const p=discoverPage-1;setDiscoverPage(p)}}>Previous</button><span>Page {discoverPage}</span><button disabled={loading || !hasMore || discoverPage>=200} onClick={()=>{const p=discoverPage+1;setDiscoverPage(p)}}>Next</button></div>
      </>}

      {tab === 'library' && <>
        {library.length ? <div className="card-grid">{library.filter(r => r.title.toLowerCase().includes(search.toLowerCase())).map(r=><RecipeCard key={r.id} {...cardProps(r)}/>)}</div> : <Empty icon={<BookOpen/>} title="Your Cookbook is empty" body="Save your favorites from Discover or a recipe preview."/>}
        {selectedCount>0 && <div className="basket-bar"><div><ShoppingBasket size={20}/><span><b>{selectedCount}</b> recipe{selectedCount===1?'':'s'} selected</span></div><button onClick={buildList}>View grocery list <span>→</span></button></div>}
      </>}

      {tab === 'grocery' && <GroceryView selected={selected} onRemove={removeFromPlan} updateServings={updateServings} onOpen={openRecipe} busy={!!importing} grocery={grocery} setGrocery={setGrocery} onBuild={buildList} loading={listLoading}/>}
    </main>
    {preview && <RecipeModal preview={preview} onClose={closeRecipe} {...cardProps(preview.recipe)}/>}
    <Toast message={toast} onClose={()=>setToast('')}/>
  </div>
}

function RecipeActions({saved, selected, busy, onSave, onAdd, onRemove}) {
  return <div className="card-actions recipe-actions">
    <button disabled={busy} onClick={saved ? onRemove : onSave}>{saved ? <Trash2 size={15}/> : <BookOpen size={15}/>} {saved ? 'Remove from Cookbook' : 'Save to Cookbook'}</button>
    <button disabled={busy || selected} onClick={onAdd}><ShoppingBasket size={15}/>{selected ? 'In Grocery List' : 'Save to Grocery List'}</button>
  </div>
}

function RecipeCard(props) {
  const {recipe, selected, onOpen} = props
  return <article className={`recipe-card ${selected ? 'selected' : ''}`}>
    <button className="recipe-open" onClick={onOpen} aria-label={`View recipe: ${recipe.title}`}>
      <div className="image-wrap">{recipe.image_url ? <img loading="lazy" src={recipe.image_url} alt=""/> : <div className="image-fallback"><Utensils/></div>}<span className="source-pill">{recipe.source || 'Recipe'}</span></div>
      <div className="card-body"><h3>{recipe.title}</h3></div>
    </button>
    <div className="card-body card-footer"><RecipeActions {...props}/></div>
  </article>
}

function RecipeModal({preview, onClose, ...actions}) {
  const dialog = useRef(null)
  const {recipe, loading, error} = preview
  useEffect(() => {
    const previous = document.activeElement
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialog.current.showModal()
    return () => { document.body.style.overflow = overflow; previous?.focus() }
  }, [])
  return <dialog ref={dialog} className="recipe-modal" aria-labelledby="recipe-modal-title" onCancel={e => {e.preventDefault(); onClose()}} onClick={e => {if(e.target === dialog.current) onClose()}}>
    <div className="modal-content">
      <button className="modal-close ghost" onClick={onClose} aria-label="Close recipe"><X/></button>
      <h2 id="recipe-modal-title">{recipe.title}</h2>
      {loading ? <Loading/> : error ? <p role="alert">{error}</p> : <>
        {recipe.image_url && <img className="modal-image" src={recipe.image_url} alt=""/>}
        <p>{recipe.description}</p>
        <div className="meta">{recipe.servings && <span>{recipe.servings} servings</span>}{recipe.total_minutes && <span>{recipe.total_minutes} minutes</span>}{recipe.cost_text && <span>{recipe.cost_text}</span>}</div>
        <RecipeActions {...actions}/>
        <h3>Ingredients</h3><ul>{recipe.ingredients?.map((line, i) => <li key={i}>{line}</li>)}</ul>
        <h3>Instructions</h3><ol>{recipe.instructions?.map((line, i) => <li key={i}>{line}</li>)}</ol>
      </>}
      <a href={recipe.source_url || recipe.url} target="_blank" rel="noreferrer">View Original Page <ExternalLink size={14}/></a>
    </div>
  </dialog>
}

function GroceryView({selected,onRemove,updateServings,onOpen,busy,grocery,setGrocery,onBuild,loading}) {
  const [copyStatus, setCopyStatus] = useState('')
  const [manualCopy, setManualCopy] = useState('')
  useEffect(() => { setCopyStatus(''); setManualCopy('') }, [grocery])
  useEffect(() => {
    if (copyStatus !== 'copied') return
    const timer = setTimeout(() => setCopyStatus(''), 4000)
    return () => clearTimeout(timer)
  }, [copyStatus])
  const selection = Object.values(selected)
  const checked = grocery.filter(x=>x.checked).length
  const sections = Object.entries(grocery.reduce((groups, item, index) => {
    const category = item.category || 'Other'
    ;(groups[category] ||= []).push({item, index})
    return groups
  }, {}))
  const toggleCheck = i => setGrocery(prev => prev.map((x,idx)=>idx===i?{...x,checked:!x.checked}:x))
  const copyList = async () => {
    const text = sections.map(([category, entries]) => `${category}\n${entries.map(({item}) => `${item.checked?'✓':'☐'} ${[item.quantity_display,item.unit,item.name].filter(Boolean).join(' ')}`).join('\n')}`).join('\n\n')
    setCopyStatus('copying')
    setManualCopy('')
    if (await copyText(text)) {
      setCopyStatus('copied')
    } else {
      setCopyStatus('failed')
      setManualCopy(text)
    }
  }
  return <div className="grocery-layout">
    <aside className="plan-panel"><div className="panel-title"><span>Meal Plan</span><b>{selection.length}</b></div>{selection.length ? selection.map(r=><div className="plan-recipe" key={r.id}><div><button className="plan-title" onClick={()=>onOpen(r)}>{r.title}</button><label>Servings <input type="number" min="0.5" step="0.5" key={r.servings} defaultValue={r.servings} disabled={busy} onBlur={e=>{updateServings(r.id,e.target.value); e.target.value=r.servings}}/></label></div><button disabled={busy} aria-label={`Remove ${r.title} from Meal Plan`} onClick={()=>onRemove(r.id)}><Trash2 size={16}/></button></div>) : <p className="muted">Add recipes from Discover or your Cookbook.</p>}<button className="primary wide" disabled={!selection.length||loading} onClick={onBuild}>{loading?<LoaderCircle className="spin" size={17}/>:<RefreshCw size={17}/>}Rebuild list</button></aside>
    <section className="list-panel"><div className="list-head"><div><span className="eyebrow">SHOPPING MODE</span><h2>Grocery list</h2><p>{grocery.length ? `${checked} of ${grocery.length} items checked` : 'Build a list from your selected recipes.'}</p></div>{grocery.length>0 && <button className="ghost" disabled={copyStatus==='copying'} onClick={copyList}>{copyStatus==='copied'?<><Check size={16}/>Copied!</>:copyStatus==='copying'?'Copying…':'Copy list'}</button>}</div>
      <div role="status" aria-live="polite" className="copy-status">{copyStatus==='copied'?'Grocery list copied to clipboard.':copyStatus==='failed'?'Automatic copying was blocked. Select and copy the list below.':''}</div>
      {manualCopy && <div className="manual-copy"><label htmlFor="manual-grocery-copy">Grocery list to copy</label><textarea id="manual-grocery-copy" readOnly value={manualCopy} onFocus={e=>e.target.select()}/><button className="ghost" onClick={()=>{const field=document.getElementById('manual-grocery-copy');field.focus();field.select()}}>Select all</button></div>}
      {loading ? <Loading/> : grocery.length ? <div className="grocery-items">{sections.map(([category, entries])=><section className="grocery-section" key={category} aria-label={category}><h3>{category}<span>{entries.length}</span></h3>{entries.map(({item,index})=><button key={`${item.name}-${index}`} className={`grocery-item ${item.checked?'checked':''}`} onClick={()=>toggleCheck(index)}><span className="check">{item.checked&&<Check size={15}/>}</span><span className="qty">{[item.quantity_display,item.unit].filter(Boolean).join(' ')}</span><span className="ingredient">{item.name}{item.notes?.length>0&&<small>{item.notes[0]}</small>}</span><span className="sources">{item.sources.length} recipe{item.sources.length===1?'':'s'}</span></button>)}</section>)}</div> : <Empty icon={<ShoppingBasket/>} title="No grocery list yet" body="Save a recipe to your Grocery List from Discover or your Cookbook."/>}</section>
  </div>
}

function Loading(){return <div className="loading"><LoaderCircle className="spin"/><span>Loading recipes…</span></div>}
function Empty({icon,title,body}){return <div className="empty"><div>{icon}</div><h3>{title}</h3><p>{body}</p></div>}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>)
