import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  BookOpen, ChefHat, ExternalLink, LoaderCircle, Plus, Search, ShoppingBasket,
  Sparkles, Trash2, Utensils, X, Check, RefreshCw
} from 'lucide-react'
import './styles.css'

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
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState('')
  const [url, setUrl] = useState('')
  const [selected, setSelected] = useState({})
  const [grocery, setGrocery] = useState([])
  const [toast, setToast] = useState('')

  const loadLibrary = async (q = '') => setLibrary(await api(`/api/recipes?q=${encodeURIComponent(q)}`))
  const loadDiscover = async (cat = category, page = discoverPage) => {
    setLoading(true)
    try {
      const data = await api(`/api/discover?category=${encodeURIComponent(cat)}&page=${page}`)
      setDiscover(data.items || [])
    } catch (e) { setToast(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    api('/api/categories').then(setCategories).catch(() => setCategories(['Popular','Quick','One Pot','Chicken','Vegetarian']))
    loadLibrary().catch(e => setToast(e.message))
    loadDiscover().catch(e => setToast(e.message))
  }, [])

  useEffect(() => { if (tab === 'library') loadLibrary(search).catch(e => setToast(e.message)) }, [search, tab])

  const importUrl = async (recipeUrl) => {
    if (!recipeUrl) return
    setImporting(recipeUrl)
    try {
      const recipe = await api('/api/import', { method: 'POST', body: JSON.stringify({ url: recipeUrl }) })
      await loadLibrary(search)
      setToast(`Saved ${recipe.title}`)
      setUrl('')
    } catch (e) { setToast(e.message) }
    finally { setImporting('') }
  }

  const toggle = (recipe) => {
    setSelected(prev => {
      const next = {...prev}
      if (next[recipe.id]) delete next[recipe.id]
      else next[recipe.id] = { id: recipe.id, title: recipe.title, servings: recipe.servings || 1 }
      return next
    })
  }

  const buildList = async () => {
    const recipes = Object.values(selected).map(x => ({ id: x.id, servings: Number(x.servings) }))
    if (!recipes.length) { setToast('Select at least one recipe first.'); return }
    setLoading(true)
    try {
      const data = await api('/api/grocery-list', { method: 'POST', body: JSON.stringify({ recipes }) })
      setGrocery(data.items || [])
      setTab('grocery')
    } catch (e) { setToast(e.message) }
    finally { setLoading(false) }
  }

  const selectedCount = Object.keys(selected).length
  const filteredDiscover = useMemo(() => {
    if (!search.trim()) return discover
    const q = search.toLowerCase()
    return discover.filter(x => x.title.toLowerCase().includes(q))
  }, [discover, search])

  return <div className="app-shell">
    <header>
      <div className="brand"><div className="logo"><ChefHat size={23}/></div><div><strong>Pantry Pilot</strong><span>recipes → groceries</span></div></div>
      <nav>
        <button className={tab==='discover'?'active':''} onClick={()=>setTab('discover')}><Sparkles size={17}/>Discover</button>
        <button className={tab==='library'?'active':''} onClick={()=>setTab('library')}><BookOpen size={17}/>Library <b>{library.length}</b></button>
        <button className={tab==='grocery'?'active':''} onClick={()=>setTab('grocery')}><ShoppingBasket size={17}/>Grocery list {selectedCount>0 && <b>{selectedCount}</b>}</button>
      </nav>
    </header>

    <main>
      <section className="hero">
        <div><div className="eyebrow">LOCAL-FIRST MEAL TOOL</div><h1>What sounds good?</h1><p>Browse Budget Bytes, save what you like, and turn recipes into one clean grocery list.</p></div>
        <div className="stats"><div><b>{library.length}</b><span>saved recipes</span></div><div><b>{selectedCount}</b><span>in your basket</span></div></div>
      </section>

      {tab !== 'grocery' && <div className="toolbar">
        <div className="search"><Search size={18}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder={tab==='discover'?'Filter the recipes on this page…':'Search your saved recipes…'}/>{search && <button onClick={()=>setSearch('')}><X size={16}/></button>}</div>
        <div className="url-import"><input value={url} onChange={e=>setUrl(e.target.value)} placeholder="Paste a recipe URL…"/><button disabled={!url || importing} onClick={()=>importUrl(url)}>{importing===url?<LoaderCircle className="spin" size={17}/>:<Plus size={17}/>}Import</button></div>
      </div>}

      {tab === 'discover' && <>
        <div className="category-row">
          <div className="chips">{categories.map(c => <button key={c} className={category===c?'chip active':'chip'} onClick={()=>{setCategory(c);setDiscoverPage(1);loadDiscover(c,1)}}>{c}</button>)}</div>
          <button className="ghost" onClick={()=>loadDiscover()}><RefreshCw size={16}/>Refresh</button>
        </div>
        {loading ? <Loading/> : <div className="card-grid">{filteredDiscover.map((r,i)=><DiscoverCard key={`${r.url}-${i}`} recipe={r} importing={importing===r.url} onImport={()=>importUrl(r.url)}/>)}</div>}
        <div className="pager"><button disabled={discoverPage<=1} onClick={()=>{const p=discoverPage-1;setDiscoverPage(p);loadDiscover(category,p)}}>Previous</button><span>Page {discoverPage}</span><button onClick={()=>{const p=discoverPage+1;setDiscoverPage(p);loadDiscover(category,p)}}>Next</button></div>
      </>}

      {tab === 'library' && <>
        {library.length ? <div className="card-grid">{library.map(r=><LibraryCard key={r.id} recipe={r} selected={!!selected[r.id]} onToggle={()=>toggle(r)}/>)}</div> : <Empty icon={<BookOpen/>} title="Your library is empty" body="Import a recipe from Discover or paste a recipe URL above."/>}
        {selectedCount>0 && <div className="basket-bar"><div><ShoppingBasket size={20}/><span><b>{selectedCount}</b> recipe{selectedCount===1?'':'s'} selected</span></div><button onClick={buildList}>Build grocery list <span>→</span></button></div>}
      </>}

      {tab === 'grocery' && <GroceryView selected={selected} setSelected={setSelected} grocery={grocery} setGrocery={setGrocery} onBuild={buildList} loading={loading}/>} 
    </main>
    <Toast message={toast} onClose={()=>setToast('')}/>
  </div>
}

function DiscoverCard({recipe, importing, onImport}) {
  return <article className="recipe-card discover-card">
    <div className="image-wrap">{recipe.image_url ? <img loading="lazy" src={recipe.image_url} alt=""/> : <div className="image-fallback"><Utensils/></div>}<span className="source-pill">Budget Bytes</span></div>
    <div className="card-body"><h3>{recipe.title}</h3><div className="card-actions"><a href={recipe.url} target="_blank" rel="noreferrer">View source <ExternalLink size={14}/></a><button onClick={onImport} disabled={importing}>{importing?<LoaderCircle className="spin" size={16}/>:<Plus size={16}/>}Save</button></div></div>
  </article>
}

function LibraryCard({recipe, selected, onToggle}) {
  const mins = recipe.total_minutes || ((recipe.prep_minutes||0)+(recipe.cook_minutes||0)) || null
  return <article className={`recipe-card ${selected?'selected':''}`}>
    <div className="image-wrap">{recipe.image_url ? <img loading="lazy" src={recipe.image_url} alt=""/> : <div className="image-fallback"><Utensils/></div>}<button className={`select-dot ${selected?'on':''}`} onClick={onToggle}>{selected?<Check size={17}/>:<Plus size={17}/>}</button></div>
    <div className="card-body"><h3>{recipe.title}</h3><p>{recipe.description || `${recipe.ingredients.length} ingredients`}</p><div className="meta">{recipe.servings && <span>{Number(recipe.servings).toLocaleString()} servings</span>}{mins && <span>{mins} min</span>}{recipe.cost_text && <span>{recipe.cost_text}</span>}</div><div className="card-actions"><a href={recipe.source_url} target="_blank" rel="noreferrer">Source <ExternalLink size={14}/></a><button className={selected?'selected-btn':''} onClick={onToggle}>{selected?'Selected':'Add to list'}</button></div></div>
  </article>
}

function GroceryView({selected,setSelected,grocery,setGrocery,onBuild,loading}) {
  const selection = Object.values(selected)
  const checked = grocery.filter(x=>x.checked).length
  const updateServings = (id,value) => setSelected(prev => ({...prev,[id]:{...prev[id],servings:value}}))
  const toggleCheck = i => setGrocery(prev => prev.map((x,idx)=>idx===i?{...x,checked:!x.checked}:x))
  const copyList = async () => {
    const text = grocery.map(x => `${x.checked?'✓':'☐'} ${[x.quantity_display,x.unit,x.name].filter(Boolean).join(' ')}`).join('\n')
    await navigator.clipboard.writeText(text)
  }
  return <div className="grocery-layout">
    <aside className="plan-panel"><div className="panel-title"><span>Recipes</span><b>{selection.length}</b></div>{selection.length ? selection.map(r=><div className="plan-recipe" key={r.id}><div><strong>{r.title}</strong><label>Servings <input type="number" min="0.5" step="0.5" value={r.servings} onChange={e=>updateServings(r.id,e.target.value)}/></label></div><button onClick={()=>setSelected(prev=>{const n={...prev};delete n[r.id];return n})}><Trash2 size={16}/></button></div>) : <p className="muted">Select recipes from your Library.</p>}<button className="primary wide" disabled={!selection.length||loading} onClick={onBuild}>{loading?<LoaderCircle className="spin" size={17}/>:<RefreshCw size={17}/>}Rebuild list</button></aside>
    <section className="list-panel"><div className="list-head"><div><span className="eyebrow">SHOPPING MODE</span><h2>Grocery list</h2><p>{grocery.length ? `${checked} of ${grocery.length} items checked` : 'Build a list from your selected recipes.'}</p></div>{grocery.length>0 && <button className="ghost" onClick={copyList}>Copy list</button>}</div>{grocery.length ? <div className="grocery-items">{grocery.map((item,i)=><button key={`${item.name}-${i}`} className={`grocery-item ${item.checked?'checked':''}`} onClick={()=>toggleCheck(i)}><span className="check">{item.checked&&<Check size={15}/>}</span><span className="qty">{[item.quantity_display,item.unit].filter(Boolean).join(' ')}</span><span className="ingredient">{item.name}{item.notes?.length>0&&<small>{item.notes[0]}</small>}</span><span className="sources">{item.sources.length} recipe{item.sources.length===1?'':'s'}</span></button>)}</div> : <Empty icon={<ShoppingBasket/>} title="No grocery list yet" body="Select recipes in your Library, then build the list."/>}</section>
  </div>
}

function Loading(){return <div className="loading"><LoaderCircle className="spin"/><span>Loading recipes…</span></div>}
function Empty({icon,title,body}){return <div className="empty"><div>{icon}</div><h3>{title}</h3><p>{body}</p></div>}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>)
