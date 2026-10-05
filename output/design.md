# Design: The Heritage Shop

The site now feels like the real shop at 57 Broadway: an old campus outfitter with brass trim, brick, printed paper and Yale Blue. Each change below says what we did and why it should keep shoppers around and help them buy.

## Look and feel

| What we changed | Why it helps |
|---|---|
| **Color:** warm paper (`#F5F1E8`) with a faint grain, ink-black text, brass trim (`#A8844F`), brick (`#8C3B2C`) for urgency, and Yale Blue (`#00356B`) as the one accent. | It reads as established and trustworthy, like an official campus store rather than a template. The single accent color shows shoppers what's clickable. |
| **Type:** Cormorant Garamond for headings and prices, *Graduate* (a varsity slab) for labels and plates, *Caveat* handwriting on tags, IBM Plex Mono on chat receipts, and light Inter for body text. | Each font has one job, so the hierarchy is easy to scan: the name, then the price, then the details. The varsity and handwritten touches add campus character without clutter. |
| **Hierarchy:** a black announcement bar ("Officially licensed · 57 Broadway · 64°F & mostly clear"), a "CC" brass seal logo, brass rules under section headings, and embroidered-patch category chips. | The licensing message and the address, the two reasons to trust the store, are always visible. Brass rules and patches break up long pages. |

## Product presentation

| What we changed | Why it helps |
|---|---|
| **One background for every photo.** 73 of the 102 photos were on black, and some were white photos padded with black bars. `scripts/clean_product_images.py` flood-fills the backdrop from the edges, and also fills the off-center black gaps a garment encloses (e.g. between an arm and the body). It replaces the backdrop with warm stone (`#F3EFE8`), softens the edge and re-centers every garment on a 900×900 square. The originals are kept. | The grid now looks like one professional photo shoot instead of a patchwork, which makes the whole catalogue feel more premium and makes items easy to compare. |
| **Museum-mount cards:** each photo sits on the stone mount inside a thin brass inset frame, with a varsity "plate" naming the garment type and the price in brass. | It turns a list into a curated display. The plate answers "what is this?" before the shopper reads the name. |
| **Hanging stock tags:** on a product page, each size hangs from a brass rail as a shop tag. "in stock" is shown in the accent color, low stock in brick red ("last 5!"), and sold-out tags are struck through with a hand-drawn line. Cards with only 1 or 2 sizes left get a small "Last sizes: M, XL" tag. | Stock status can be read at a glance, and "last 5!" creates honest urgency. Sold-out sizes are obvious before anyone tries to buy them. |

## Signature features

| What we built | Why it helps |
|---|---|
| **Walk into the store.** The Home hero is 57 Broadway drawn in CSS: brick, arched upper windows (one lit), a brass-framed sign, a striped awning, two display windows showing real products, and a door. Hovering a window lights it and sweeps a reflection across the glass; clicking opens that category. Hovering the door swings it open onto "Come on in," and clicking opens the chat with a welcome. | It's memorable and playful, and it gets shoppers to their first click (a category or a question) within seconds of landing. |
| **Residential college mode.** A "Your college…" picker in the nav covers all 14 colleges. Picking one recolors the site's accent: the awning, the door, links, buttons and the chat. It also changes the right shop window to that college's pieces, adds a "For Davenport" row on Home, adds a college chip on Products, and tells the chat assistant. The choice is remembered. For colleges without their own items, the site suggests Yale classics. The accent colors are our design choices, not official college colors. | Personal identity is a big reason people buy campus gear. Seeing the site in "your" colors and your college's products first makes it feel made for you. |
| **Weather-aware suggestions.** The backend fetches live New Haven weather (Open-Meteo, cached for 20 minutes) and picks a category: fleeces when it's cold or snowing, hoodies in rain, quarter-zips when crisp, crewnecks when mild, tees when warm. Home shows "Today on Broadway · 64°F, mostly clear — Perfect crewneck weather" with 4 in-stock picks. The chat gets a "What should I wear today?" chip and knows the weather. | It's a timely reason to buy today, it's unmistakably local, and it adds a new product row to the homepage every visit. |
| **Pop-up confirmations.** Logging out shows *"You're logged out, Test. Your chat is saved for next time. See you on Broadway."* Logging in, creating an account and switching college mode also get a pop-up. They slide in, dismiss themselves after about 4 seconds, and are announced to screen readers. | Shoppers know an action worked, especially logging out on a shared computer, and the warm wording invites them back. |

## Chat feel: "The Shop Counter"

| What we changed | Why it helps |
|---|---|
| The panel is titled **The Shop Counter** with a brass "CC" seal. Assistant replies look like notes on lightly ruled paper with a brass margin. A three-dot "typing" pulse shows while it answers. The "Ask the shop" button has a small brass bell that rings twice when the page loads. | It feels like talking to a shop associate, not a support widget, so more shoppers try it. |
| **Receipt-style recommendations:** product picks print out as a torn-edge receipt: "CAMPUS CUSTOMS · 57 BROADWAY", each item with a thumbnail, dot leaders and price, and "THANK YOU, BULLDOG" at the bottom. Every line links to the product. | It's distinctive and easy to screenshot or share, and it presents suggestions like a shopping list that's one tap from checkout. |

## Motion and micro-interactions

- Nav links get a dashed "stitched" underline that sews itself in on hover.
- Buttons fill with the accent color from left to right.
- Cards lift, the photo zooms slightly, and the brass frame tightens.
- Tags swing on hover.
- The storefront's lit window flickers softly, and its "Open" sign sways.
- Chat messages rise in, and receipts "print" from the top.

All motion is short (under 1 second) and turns off for shoppers who set "reduce motion." Small touches like these make the site feel crafted, which builds trust and keeps people browsing.

## Also

- On phones, the header scrolls away and the announcement bar shrinks to one line, so products get the screen.
- Image URLs now include a version (`?v=clean-3`), so returning visitors see the cleaned photos instead of cached old ones.
