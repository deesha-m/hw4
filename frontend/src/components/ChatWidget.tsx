import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  clearChatHistory,
  fetchChatHistory,
  formatPrice,
  sendChatMessage,
  type ChatMessage,
  type ChatProduct,
  type PageContext,
} from '../api.ts'
import { useAuth } from '../auth.tsx'
import { useChatResults } from '../chatResults.tsx'
import { useCollege } from '../college.tsx'

// Some saved replies use **bold**; show it as bold instead of raw asterisks.
function renderText(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )
}

// One-tap questions that fit the page the shopper is on (and their college, if set).
function suggestionsFor(path: string, college: string | null): string[] {
  if (/^\/products\/[^/]+$/.test(path)) {
    return ['Is this in stock in M?', 'What colors does this come in?', 'Show me similar items']
  }
  if (path === '/products') {
    return ['What hoodies do you have?', 'Tees under $35', "What's in stock in size S?"]
  }
  return [
    'What should I wear today?',
    college ? `Anything for ${college}?` : 'What hoodies do you have?',
    'Gift for a Yale parent under $60',
  ]
}

type Entry = ChatMessage & { products?: ChatProduct[]; pageNote?: string; error?: boolean }

// Chat entries belong to whoever was logged in when they were written ('guest' otherwise), so
// logging in shows that account's saved history and logging out hides it.
type Conversation = { owner: string; entries: Entry[] }

// Product picks print like a shop receipt: item, dot leaders, price.
function Receipt({ products }: { products: ChatProduct[] }) {
  return (
    <div className="receipt">
      <div className="receipt-head">Campus Customs · 57 Broadway</div>
      {products.map((product) => (
        <Link key={product.product_id} to={`/products/${product.product_id}`} className="receipt-row">
          <img src={product.image_url} alt="" />
          <span className="receipt-name">{product.name}</span>
          <span className="receipt-dots" aria-hidden="true" />
          <span className="receipt-price">
            {product.total_stock === 0 ? 'Sold out' : formatPrice(product.price)}
          </span>
        </Link>
      ))}
      <div className="receipt-foot">Thank you, Bulldog</div>
    </div>
  )
}

export default function ChatWidget() {
  const { user } = useAuth()
  const { college } = useCollege()
  const { results, show } = useChatResults()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [welcomed, setWelcomed] = useState(false) // came in through the storefront door
  const owner = user ? `user-${user.id}` : 'guest'
  const [conversation, setConversation] = useState<Conversation>({ owner: 'guest', entries: [] })
  const entries = conversation.owner === owner ? conversation.entries : []
  const setEntries = (next: Entry[]) => setConversation({ owner, entries: next })
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)
  const sendRef = useRef<(text: string) => void>(() => {})

  // A returning logged-in shopper gets their saved chat back from the database.
  useEffect(() => {
    if (!user) return
    let cancelled = false
    fetchChatHistory().then((saved) => {
      if (cancelled) return
      setConversation({
        owner: `user-${user.id}`,
        entries: saved.map((m) => ({ role: m.role, content: m.content, products: m.products })),
      })
    })
    return () => {
      cancelled = true
    }
  }, [user])

  // Other parts of the site (the storefront door) can open the chat.
  useEffect(() => {
    function handleOpen(event: Event) {
      const message = (event as CustomEvent<{ message?: string }>).detail?.message
      setOpen(true)
      setWelcomed(true)
      if (message) sendRef.current(message)
    }
    window.addEventListener('cc:open-chat', handleOpen)
    return () => window.removeEventListener('cc:open-chat', handleOpen)
  }, [])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [conversation, sending, open])

  const name = user ? ` ${user.first_name}` : ''
  const greeting = welcomed
    ? `Come on in${name ? `,${name}` : ''}! Welcome to 57 Broadway. What can I help you find today?`
    : `Hi${name}! I'm at the shop counter. Ask me about sizes, colors, stock or gift ideas${college ? ` for ${college}` : ''}.`

  // What the shopper is looking at right now, so "this" and "the second one" make sense.
  function pageContext(): PageContext {
    const path = location.pathname
    const productMatch = path.match(/^\/products\/([^/]+)$/)
    const showingResults = path === '/products' && results !== null
    return {
      path,
      product_id: productMatch ? decodeURIComponent(productMatch[1]) : null,
      results_title: showingResults ? results.title : null,
      visible_product_ids: showingResults ? results.products.slice(0, 12).map((p) => p.product_id) : [],
      college,
    }
  }

  async function handleClear() {
    await clearChatHistory()
    setEntries([])
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    void send(draft)
  }

  async function send(raw: string) {
    const text = raw.trim()
    if (!text || sending) return

    // Guests send their recent turns; for logged-in shoppers the backend reads saved history.
    const history: ChatMessage[] = user
      ? []
      : entries.filter((entry) => !entry.error).map(({ role, content }) => ({ role, content }))
    const next: Entry[] = [...entries, { role: 'user', content: text }]
    setEntries(next)
    setDraft('')
    setSending(true)
    try {
      const reply = await sendChatMessage(text, history, pageContext())
      let pageNote: string | undefined
      if (reply.page) {
        // The agent ran a browse search: put the matches on the Products page as cards.
        show(reply.page)
        if (location.pathname !== '/products') navigate('/products')
        pageNote = `${reply.page.title} · ${reply.page.products.length} on the page`
      }
      setEntries([...next, { role: 'assistant', content: reply.reply, products: reply.products, pageNote }])
    } catch (err) {
      setEntries([...next, { role: 'assistant', content: (err as Error).message, error: true }])
    } finally {
      setSending(false)
    }
  }
  // The door's open-chat event needs the latest send(), so keep it in a ref.
  useEffect(() => {
    sendRef.current = (text) => void send(text)
  })

  return (
    <div className="chat">
      {open && (
        <section className="chat-panel" aria-label="Chat with Campus Customs">
          <header className="chat-header">
            <span className="chat-seal" aria-hidden="true">
              CC
            </span>
            <div className="chat-title">
              <strong>The Shop Counter</strong>
              <span>{user ? 'Your chat is saved to your account' : 'Log in to save your chat'}</span>
            </div>
            <div className="chat-header-actions">
              {user && entries.length > 0 && (
                <button type="button" className="chat-clear" onClick={handleClear}>
                  Clear
                </button>
              )}
              <button type="button" className="icon-button" onClick={() => setOpen(false)} aria-label="Close chat">
                ×
              </button>
            </div>
          </header>
          <div className="chat-messages" ref={listRef}>
            <div className="chat-entry assistant">
              <div className="bubble assistant">{greeting}</div>
            </div>
            {entries.map((entry, index) => (
              <div key={index} className={`chat-entry ${entry.role}`}>
                <div className={`bubble ${entry.role} ${entry.error ? 'error' : ''}`}>{renderText(entry.content)}</div>
                {entry.pageNote && (
                  <Link to="/products" className="chat-page-note">
                    {entry.pageNote} →
                  </Link>
                )}
                {entry.products && entry.products.length > 0 && <Receipt products={entry.products} />}
              </div>
            ))}
            {sending && (
              <div className="chat-entry assistant">
                <div className="bubble assistant typing" aria-label="The shop is typing">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>
          {!sending && (
            <div className="chat-suggestions" aria-label="Suggested questions">
              {suggestionsFor(location.pathname, college).map((question) => (
                <button key={question} type="button" className="chat-chip" onClick={() => void send(question)}>
                  {question}
                </button>
              ))}
            </div>
          )}
          <form className="chat-input" onSubmit={handleSubmit}>
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask the shop…"
              aria-label="Message"
              maxLength={1000}
            />
            <button type="submit" className="button" disabled={sending || !draft.trim()}>
              Send
            </button>
          </form>
        </section>
      )}
      <button
        type="button"
        className={`chat-toggle ${open ? 'is-open' : ''}`}
        onClick={() => setOpen((value) => !value)}
        aria-label={open ? 'Close chat' : 'Open chat'}
      >
        {open ? (
          '×'
        ) : (
          <>
            <span className="bell" aria-hidden="true" />
            Ask the shop
          </>
        )}
      </button>
    </div>
  )
}
