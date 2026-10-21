/* ================= MOCK DATA ================= */
const REELS = [
  { title: '3 mistakes ruining your aesthetic reel', tone: 0, duration: '0:32',
    m: { views: ['90K', 32], likes: ['504', 25], shares: ['281', 35], comments: ['98', 90] },
    cmp: 'Arrows compare actual results with Curo’s pre-publish simulation. Public counts only.',
    phase: { name: 'Peak phase', range: '1 – 3 days', idx: 1, desc: 'Views are climbing fast and are already 3× your follower count, so it’s reaching people beyond your followers.' },
    audience: [
      { t: 'Comments are driving engagement', d: 'This topic is sparking conversations. People find it relatable and are sharing their thoughts in the comments.' },
      { t: 'Shares are lower than usual', d: 'This reel isn’t being shared much, which suggests it may not feel highly shareable or actionable for your audience.' },
      { t: 'People are tagging friends', d: 'Many comments tag someone, which usually means viewers think the tips are worth passing on.' } ],
    top: { handle: '@aesthetic.anya', text: 'Mistake #2 is literally me every single time. Saving this.', likes: '214 likes · 18 replies' } },
  { title: 'Get ready with me: Navratri edition', tone: 1, duration: '0:45',
    m: { views: ['41K', -8], likes: ['1.2K', 14], shares: ['96', 6], comments: ['142', 38] },
    cmp: 'Arrows compare actual results with Curo’s pre-publish simulation. Public counts only.',
    phase: { name: 'Plateau', range: '4 – 9 days', idx: 2, desc: 'Views have levelled off. New views are arriving slowly, at about your usual pace.' },
    audience: [
      { t: 'Comments are asking “where is it from?”', d: 'Most comments are product questions, so people liked the outfit more than the routine itself.' },
      { t: 'Shares are lower than usual', d: 'GRWM formats give people less reason to send them on than step-by-step styling.' },
      { t: 'Likes are steady', d: 'Your regulars engaged as usual, but it didn’t travel far beyond them.' } ],
    top: { handle: '@meera.styles', text: 'Please drop the link for the lehenga, I need it before Dussehra.', likes: '96 likes · 11 replies' } },
  { title: 'One kurta, five dupattas', tone: 2, duration: '0:28',
    m: { views: ['128K', 46], likes: ['6.8K', 52], shares: ['940', 61], comments: ['210', 18] },
    cmp: 'Arrows compare actual results with Curo’s pre-publish simulation. Public counts only.',
    phase: { name: 'Second wave', range: 'Day 6+', idx: 1, desc: 'Views picked up again on day 6 after slowing down — a second wave is bringing in new viewers.' },
    audience: [
      { t: 'Shares are your best this quarter', d: 'People are sending it as a reference to recreate the looks — 4.1× your median shares.' },
      { t: 'Likes are well above usual', d: 'Likes per view are 1.6× your usual, and many comments tag the person they’d style it for.' },
      { t: 'Comments are steady', d: 'Comments are mostly people picking their favourite dupatta.' } ],
    top: { handle: '@twirlwithtara', text: 'The mustard one!! Doing this for my cousin’s mehendi.', likes: '388 likes · 24 replies' } },
  { title: 'Thrift haul under ₹2,000', tone: 3, duration: '0:52',
    m: { views: ['22K', -31], likes: ['610', -22], shares: ['40', -18], comments: ['61', 5] },
    cmp: 'Arrows compare actual results with your 30-day average (no simulation was run). Public counts only.',
    phase: { name: 'Decline', range: 'Day 10+', idx: 3, desc: 'New views have slowed to a trickle. This reel has mostly run its course.' },
    audience: [
      { t: 'Likes per view are low', d: 'Fewer viewers liked it than usual; the intro runs long before the first item appears.' },
      { t: 'Comments are about prices', d: 'People asked where to buy, which suggests interest in budget content even though this reel underperformed.' },
      { t: 'Shares are lower than usual', d: 'Hauls give people less to pass on than styling how-tos.' } ],
    top: { handle: '@budgetbae.in', text: 'Which market is this? Need a budget festive one next!', likes: '57 likes · 9 replies' } }
];

const OPPS = [
  { id: 'ganpati', tag: 'Competitor', tagBg: '#F2D4E2', tagFg: '#242424', score: 8, fest: 'Ganpati',
    card: 'Ganpati dress ideas are picking up in your niche — 6 creators you track posted about them this week.',
    title: 'Ganpati dress ideas', short: 'Ganapati dress ideas',
    why: 'Competitors + niche + rising searches. Pick a direction or write your own.',
    summary: 'A few creators you track recently posted about Ganpati dress ideas, and this topic also matches your niche. It could be a relevant and timely idea for you to explore.',
    signals: ['Competitors', 'Your niche', 'Trend'],
    handles: ['@theoutfitdiaries', '@stylewithrhea', '@mumbaiwardrobe'], more: 'and 3 more creators you track',
    compText: 'They’ve recently posted about Ganpati outfit ideas — from traditional looks to modern styled fits. Since this aligns with your niche and is trending right now, it could be a good opportunity for you.',
    fit: [ { k: 'Your content', t: 'Your festive styling reels average 2.3× your usual shares.' },
           { k: 'Trend', t: 'Ganpati outfit reels in your niche are up 3.4× week on week.' },
           { k: 'Timing', t: 'Festive outfit content peaks in the 10 days before the festival.' } ],
    ideas: [
      { id: 'g1', key: 'g3', title: 'Styling the same outfit 3 different ways for Ganpati.', why: 'Re-styling reels are your top format for shares.', desc: 'Create a video showcasing creative and beautiful outfit ideas for Ganpati, including different themes, colour combinations and styling tips.' },
      { id: 'g2', title: 'What I wore for Ganpati last year vs this year.', why: 'Comparison formats drive comments for creators like you.', desc: 'A side-by-side of last year’s festive look and this year’s — what changed, what stayed, and why.' },
      { id: 'g3', title: 'Quick prasad recipes you can make in under 10 minutes.', why: 'Trending, but outside your usual niche — lower creator fit.', desc: 'Three fast prasad recipes for the festival week, each shot in one take in your kitchen.' } ] },
  { id: 'reveal', tag: 'Competitor', tagBg: '#F2D4E2', tagFg: '#242424', score: 7, fest: 'the festive season',
    card: 'Show the finished look for 1.2 seconds, then cut to the messy getting-ready chaos behind it.',
    title: 'The final-look-first reveal', short: 'Final-look-first reveal',
    why: 'Peers are flipping before → after. It creates a curiosity gap in the first second.',
    summary: 'Creators in your niche are opening on the finished look and then rewinding to the process. It flips your usual before-to-after order and creates a curiosity gap in the very first second.',
    signals: ['Competitors', 'Format'],
    handles: ['@stylewithrhea', '@thedrapestory', '@kavyawears'], more: 'and 4 more creators you track',
    compText: 'Their reveal-first reels got 1.9× their usual views this month.',
    fit: [ { k: 'Your content', t: 'Your best reel showed all five looks in its first second.' },
           { k: 'Audience', t: 'Your reels that open on the “before” get 0.7× your usual views.' },
           { k: 'Trend', t: '1,100+ reveal-first fashion reels in the last 30 days.' } ],
    ideas: [
      { id: 'r1', title: 'Final look first, messy room after: my real Ganpati getting-ready.', why: 'Matches the opening of your strongest reel.', desc: 'Open on the finished look, then rewind through the chaos of getting there.' },
      { id: 'r2', title: 'The 1.2-second reveal: festive look, then behind the scenes.', why: 'Reveal-first openings are getting peers well above their usual views.', desc: 'A quick flash of the final look before the real process starts.' },
      { id: 'r3', title: 'What my outfit looks like vs what it took.', why: 'Relatable tension tends to drive comments for you.', desc: 'The polished result next to the honest effort behind it.' } ] },
  { id: 'mistakes', tag: 'Trend', tagBg: '#242424', tagFg: '#FFFFFF', score: 7, fest: 'the festive season',
    card: 'Educational “mistakes” reels are performing 1.8× higher than GRWMs in your niche this month.',
    title: '“Mistakes” explainers', short: 'Styling “mistakes” explainers',
    why: 'Your own “3 mistakes” reel is peaking and the format is rising across fashion.',
    summary: 'Your own “3 mistakes ruining your aesthetic reel” is in its peak phase, and the format is rising across fashion creators. A styling-mistakes version would play to both.',
    signals: ['Trend', 'Your content'],
    handles: ['@theoutfitdiaries', '@styledbysana', '@mumbaiwardrobe'], more: 'and 2 more creators you track',
    compText: 'They’ve turned common styling errors into quick fixes. Viewers share them as checklists.',
    fit: [ { k: 'Your content', t: '“3 mistakes ruining your aesthetic reel” is in its peak phase now.' },
           { k: 'Trend', t: '“Mistakes” formats are up 1.8× vs GRWMs in your niche.' },
           { k: 'Audience', t: 'Your how-tos get 2× the shares of your hauls.' } ],
    ideas: [
      { id: 'm1', title: '3 mistakes making your ethnic outfit look cheap.', why: 'Same structure as your current peak reel.', desc: 'Three quick fixes that make an everyday ethnic look feel elevated.' },
      { id: 'm2', title: 'Dupatta mistakes everyone makes (and quick fixes).', why: 'Dupatta styling is your most-shared topic.', desc: 'Common draping errors and the 5-second fix for each.' },
      { id: 'm3', title: 'Stop doing this with festive jewellery.', why: 'Short, punchy hooks perform well for you.', desc: 'Jewellery pairing mistakes and what to do instead.' } ] },
  { id: 'secondwave', tag: 'Your content', tagBg: '#C3BFF2', tagFg: '#242424', score: 7, fest: 'the festive season',
    card: '“One kurta, five dupattas” is in a second wave — a follow-up could ride its momentum.',
    title: 'Follow up a second wave', short: 'Follow-up to a second wave',
    why: 'Your best reel is getting a second push. A sequel can borrow its audience.',
    summary: '“One kurta, five dupattas” picked up a second wave of views on day 6. People finding it now haven’t seen your other work, so a direct follow-up could turn them into followers.',
    signals: ['Your content', 'Audience'],
    handles: ['@twirlwithtara', '@meera.styles', '@budgetbae.in'], more: 'commenters asking for part 2',
    compText: '24 comments on the original ask for a part 2 or for where each dupatta is from.',
    fit: [ { k: 'Your content', t: '128K views and 940 shares — your strongest reel this quarter.' },
           { k: 'Audience', t: 'People asking for part 2 in comments.' },
           { k: 'Timing', t: 'Second waves usually last 4–6 days for creators your size.' } ],
    ideas: [
      { id: 's1', title: 'One kurta, five dupattas — part 2: the festive edition.', why: 'Directly answers part-2 requests.', desc: 'Same format, new dupattas, styled for festive days.' },
      { id: 's2', title: 'You asked: where every dupatta is from.', why: 'Answers the most common comment.', desc: 'A quick sourcing rundown with prices for each dupatta.' },
      { id: 's3', title: 'Same kurta, five dupattas — rated by my mom.', why: 'Adds a character, which drives comments for peers.', desc: 'Your mom reacts to and rates each look.' } ] },
  { id: 'budget', tag: 'Audience', tagBg: '#E4E4EC', tagFg: '#242424', score: 6, fest: 'Ganpati',
    card: 'Your comments keep asking for budget versions — a “festive looks under ₹1,500” reel answers them.',
    title: 'Festive looks on a budget', short: 'Festive looks on a budget',
    why: 'Built from your comment section, not from trends.',
    summary: 'Across your last 10 reels, 61 comments asked about prices or cheaper alternatives. A budget-focused festive reel answers a demand your audience has already voiced.',
    signals: ['Audience', 'Comments'],
    handles: ['@budgetbae.in', '@meera.styles', '@aesthetic.anya'], more: 'and 58 more commenters',
    compText: 'Price questions are your most common comment type this month.',
    fit: [ { k: 'Audience', t: '61 price questions across your last 10 reels.' },
           { k: 'Your content', t: 'Your haul underperformed — a styling angle may fit better than a haul.' },
           { k: 'Timing', t: 'Festive shopping intent is high right now.' } ],
    ideas: [
      { id: 'b1', title: 'Festive looks under ₹1,500, head to toe.', why: 'Directly answers price questions.', desc: 'Three complete festive looks with the price of every piece.' },
      { id: 'b2', title: 'A Ganpati outfit on a ₹500 challenge.', why: 'Challenge formats drive comments for peers.', desc: 'Can you build a festive look for ₹500? Find out.' },
      { id: 'b3', title: 'Expensive-looking festive outfits that aren’t.', why: 'Styling angle — closer to your top shares.', desc: 'How to make affordable pieces look elevated.' } ] }
];

const IDEA_BANK = {
  budget: [ { title: '3 Ganpati looks under ₹1,500 — all from one market haul.', why: 'Answers the price questions in your comments.' },
            { title: 'Rewearing my Diwali outfit for Ganpati (and nobody noticed).', why: 'Rewear stories drive comments for you.' },
            { title: 'Festive look on a budget: the ₹500 accessories doing the heavy lifting.', why: 'Accessory focus keeps it about styling.' } ],
  family: [ { title: 'Twinning with my niece: 3 Ganpati looks, big and small.', why: 'Adding a character drives comments for peers.' },
            { title: 'Kids’ Ganpati outfits that survive the whole pooja.', why: 'Practical angle — likely shares.' },
            { title: 'My mom styles my outfit, I style hers.', why: 'Swap formats spark comments and shares.' } ],
  prep: [ { title: 'My 10-minute Ganpati morning: outfit, thali, done.', why: 'Routine formats hold attention for your audience.' },
          { title: 'Decorating the mandap corner with what I already own.', why: 'Adjacent to your niche — moderate fit.' },
          { title: 'What’s in my bag for pandal hopping.', why: 'List formats are easy to share.' } ],
  home: [ { title: 'Three Ganpati looks from my own wardrobe — no shopping.', why: 'Easy to shoot at home; matches your re-styling hits.' },
          { title: 'One saree, three drapes, shot in my bedroom in 15 minutes.', why: 'Drape tutorials are your most-saved topic.' },
          { title: 'Getting ready for aarti in 60 seconds.', why: 'Short and timely — good for new audiences.' } ]
};

const TONES = [{ bg: '#C3BFF2' }, { bg: '#E4E4EC' }, { bg: '#F2D4E2' }, { bg: '#FFFFFF' }, { bg: '#E4E4EC' }];

const ANN = {
  hook: { title: 'Strong hook', desc: 'Grabs attention in the first few seconds and makes people want to keep watching.', ev: 'Your reels that open with a question or a promise got 1.8× the views of your other openings (last 48 reels).' },
  comments: { title: 'Drives comments', desc: 'Encourages people to comment their favourite look.', ev: 'Pick-one prompts brought 2.1× your usual comments on “Get ready with me: Navratri edition”.' },
  saves: { title: 'Drives likes', desc: 'A satisfying finished look is what people tap like on.', ev: 'Your reels that end on the finished look get 1.7× your median likes: “One kurta, five dupattas” got 6.8K likes.' },
  shares: { title: 'Encourages shares', desc: 'Makes it share-worthy and sparks engagement.', ev: 'Among 1,240 similar posts this month, endings that name a friend or an occasion were shared 1.6× more.' }
};

const G3 = {
  roles: ['hook', 'look1', 'look2', 'look3', 'cta'],
  anns: { hook: 'hook', look1: 'comments', look2: null, look3: 'saves', cta: 'shares' },
  versions: [
    { hook: 'Same outfit, 3 different Ganpati looks? Let me show you!', look1: 'Look 1 – Traditional vibes.', look2: 'Look 2 – A modern twist.', look3: 'Look 3 – Festive and fun.', cta: 'Which look is your favourite? Comment below!' },
    { hook: 'I only bought one outfit for Ganpati. Here are three ways I’m wearing it.', look1: 'Look 1 – Morning aarti: classic and simple.', look2: 'Look 2 – Pandal hopping: jacket on, sneakers in.', look3: 'Look 3 – Evening celebrations: all the jewellery.', cta: '1, 2 or 3 — which one are you wearing? Tell me below.' },
    { hook: 'Stop buying a new outfit for every day of Ganpati. Watch this.', look1: 'Look 1 – Traditional, with my mom’s dupatta.', look2: 'Look 2 – Modern: belted, layered, done.', look3: 'Look 3 – Festive: flowers in the hair, bold earrings.', cta: 'Save this for festival week — and comment your pick.' }
  ],
  conv: { hook: 'Okay so I didn’t buy anything new for Ganpati — I’m wearing this one outfit three ways.', look1: 'First up, the classic: kurta, dupatta, jhumkas. Done.', look2: 'Now throw a denim jacket on top — suddenly it’s a whole new vibe.', look3: 'And for the evening? Flowers, big earrings, full festive mode.', cta: 'Be honest — which one’s your favourite? Tell me below.' },
  short: { hook: 'One outfit. Three Ganpati looks.', look1: 'Traditional.', look2: 'Modern.', look3: 'Festive.', cta: '1, 2 or 3? Comment below.' },
  hooks: ['Same outfit, 3 Ganpati looks — and look 3 is my favourite.', 'POV: you have one outfit and three Ganpati plans.', 'Don’t buy a new outfit for Ganpati until you’ve seen this.'],
  ctas: ['Which look is your favourite? Comment 1, 2 or 3!', 'Save this for festival week — you’ll thank me.', 'Send this to the friend you’re twinning with this Ganpati.'],
  editHook: 'Wait for look 3. Same outfit, three Ganpati looks — starting from the end.',
  editLook2: 'Look 2 – A modern twist: swap the dupatta for a denim jacket.',
  editCta: 'Send this to the friend you’re twinning with — and tell me your pick.'
};

const GEN = {
  hooks: [ t => t + ' Watch till the end.', t => 'Nobody talks about this: ' + lc(t), t => 'I tried this so you don’t have to — ' + lc(t) ],
  p1: ['Part 1 – where it starts.', 'First, the before.', 'Step one — the setup.'],
  p2: ['Part 2 – the reveal.', 'Then the switch that changes everything.', 'Step two — the result.'],
  ctas: ['Would you try this? Tell me below.', 'Save this for later — you’ll need it.', 'Send this to someone who needs it.'],
  conv: { p1: 'So here’s where I started…', p2: 'And honestly? This is where it clicked.', cta: 'Would you try it? Tell me in the comments.' },
  short: { p1: 'Before.', p2: 'After.', cta: 'Try it? Comment below.' }
};

const FR = {
  hook: { sketch: 'closeup', instr: 'Start with a close-up shot showing the outfit detail as you pick it up.', shot: 'Close-up · handheld', onScreen: '1 outfit. 3 Ganpati looks.', trans: 0 },
  look1: { sketch: 'look1', instr: 'Step back to a full-length mirror shot in the traditional look — dupatta over one shoulder, jhumkas on.', shot: 'Full-length · tripod at chest height', onScreen: 'Look 1 · Traditional', trans: 1 },
  look2: { sketch: 'look2', instr: 'Same spot, same framing — now with a denim jacket over the kurta and a belt at the waist. Hold for two beats.', shot: 'Full-length · same tripod mark', onScreen: 'Look 2 · A modern twist', trans: 2 },
  look3: { sketch: 'look3', instr: 'Hang the marigold strings behind you and twirl into the festive look with statement earrings.', shot: 'Medium-wide · slightly low angle', onScreen: 'Look 3 · Festive & fun', trans: 3 },
  cta: { sketch: 'cta', instr: 'Walk up close to the camera and count 1, 2, 3 on your fingers as you ask the question.', shot: 'Close-up · eye level, direct to camera', onScreen: '1, 2 or 3? Comment below', trans: 5 }
};
const FR_ALT = {
  hook: { sketch: 'flatlay', instr: 'Open on a top-down shot of the outfit laid flat on your bed, then reach in and pick up the dupatta.', shot: 'Overhead · phone on a shelf above', onScreen: '1 outfit. 3 Ganpati looks.', trans: 4 },
  look1: { sketch: 'mirror', instr: 'Film the traditional look as a mirror selfie — phone at chest height, turn once to show the drape.', shot: 'Mirror selfie · handheld', onScreen: 'Look 1 · Traditional', trans: 1 },
  look2: { sketch: 'mirror', instr: 'Mirror selfie again, but step in close for the jacket and belt detail before pulling back.', shot: 'Mirror selfie · push in, pull out', onScreen: 'Look 2 · A modern twist', trans: 4 },
  look3: { sketch: 'mirror', instr: 'Shoot the festive look in the mirror with fairy lights on, then tilt down to the earrings.', shot: 'Mirror selfie · tilt down', onScreen: 'Look 3 · Festive & fun', trans: 3 },
  cta: { sketch: 'triptych', instr: 'End on a quick split-screen of all three looks while you ask which one wins.', shot: 'Edit · three-way split screen', onScreen: '1, 2 or 3?', trans: 5 }
};
const FR_E1 = { sketch: 'rewind', instr: 'Open on Look 3 for one second, then hit a rewind effect back to the plain outfit in your hands.', shot: 'Medium-wide → close-up', onScreen: 'Wait for look 3…' };
const GEN_INSTR = {
  hook: 'Open close on the key detail as you say the hook.',
  look1: 'Show the starting point — the “before” — in one steady shot.',
  look2: 'Reveal the result. Hold the final frame for a beat so viewers can take it in.',
  look3: 'Show the payoff from a second angle so it feels complete.',
  cta: 'Come close to the camera and ask the question directly.'
};
const EASY = {
  hook: 'Easier take: prop your phone on a shelf and record your hands picking up the outfit in one continuous shot.',
  look1: 'Easier take: phone propped at waist height, step into frame, turn once, step out. One take.',
  look2: 'Easier take: keep the phone where it is — just swap the layer off-camera and step back in.',
  look3: 'Easier take: skip the backdrop; a single twirl in natural light near a window is enough.',
  cta: 'Easier take: sit down, phone at eye level, and say the line once. No movement needed.'
};
const TRANSITIONS = ['Snap cut on the beat', 'Spin transition', 'Jump cut', 'Whip pan', 'Match cut on the hand', 'Hold, then end card'];

const CAPTIONS = {
  base: [ { t: 'One outfit, three Ganpati moods — traditional, modern, festive. Which one is you? Tell me below.', why: 'Ends on a pick-one question → comments' },
          { t: 'Didn’t buy anything new for Ganpati. Styled one outfit three ways instead. Save this for festival week.', why: 'Save prompt → useful ask, though saves aren’t public' },
          { t: 'Look 1, 2 or 3? Same outfit, completely different vibe. Send this to the friend you’re twinning with.', why: 'Names a friend → built for shares' } ],
  short: [ { t: '1 outfit. 3 Ganpati looks. Pick yours.', why: 'Short → reads before “more”' },
           { t: 'Same outfit, three moods. Save for later.', why: 'Save prompt' },
           { t: 'Ganpati, sorted — three ways. Which one?', why: 'Question → comments' } ],
  playful: [ { t: 'My wardrobe said “you have nothing to wear”. I said “watch me”. Three Ganpati looks, one outfit.', why: 'Relatable tension → comments' },
             { t: 'Plot twist: it’s the same outfit every time. Which look fooled you?', why: 'Curiosity → comments' },
             { t: 'Rate my Ganpati looks 1–10. Be nice (or don’t).', why: 'Invites replies → comments' } ],
  question: [ { t: 'Traditional, modern or festive — what are you wearing this Ganpati?', why: 'Open question → comments' },
              { t: 'Would you rewear one outfit for all of Ganpati? Here’s how I’d do it.', why: 'Opinion question → comments' },
              { t: 'Which look should I wear for the visarjan? Help me decide.', why: 'Asks for help → comments' } ]
};
const HASHTAGS = [ { t: '#ganpatioutfit', k: 'niche' }, { t: '#ganeshchaturthi', k: 'broad' }, { t: '#oneoutfitthreeways', k: 'niche' }, { t: '#festivelook', k: 'broad' }, { t: '#ethnicstyling', k: 'niche' }, { t: '#mumbaistyle', k: 'local' }, { t: '#outfitideas', k: 'broad' }, { t: '#indianwear', k: 'broad' } ];

const SIM_EDITS = [
  { id: 'e1', title: 'Open on Look 3, then rewind', desc: 'Show the finished festive look for one second before going back to the plain outfit.', gain: 5, frame: 0, frameLabel: 'Frame 1 · Hook' },
  { id: 'e2', title: 'Give Look 2 a reason to stay', desc: 'Add an on-screen tip — “swap the dupatta for a jacket” — so the middle has a takeaway.', gain: 3, frame: 2, frameLabel: 'Frame 3 · Look 2' },
  { id: 'e3', title: 'End with a send prompt', desc: 'Ask viewers to send it to the friend they’re twinning with, not only to comment.', gain: 4, frame: 4, frameLabel: 'Frame 5 · Ending' }
];
const WORKING = [
  { t: 'Your topic closely matches content that has generated above-average shares for you.',
    ev: [ { tone: 2, who: 'Your reel', title: 'One kurta, five dupattas', stat: '940 shares · 4.1× your median' },
          { tone: 0, who: 'Your reel', title: '3 mistakes ruining your aesthetic reel', stat: '281 shares · +35% vs simulation' } ] },
  { t: 'Your “one item, many looks” structure matches your three strongest reels.',
    ev: [ { tone: 2, who: 'Your reel', title: 'One kurta, five dupattas', stat: '128K views · second wave on day 6' },
          { tone: 1, who: '@stylewithrhea', title: '1 saree, 4 drapes', stat: '410K views · 1.8× her baseline' } ] }
];
const HOLDING = [
  { id: 'e1', t: 'Your hook is similar to your average-performing reels. Your strongest reels open on the finished result, which creates a curiosity gap.', frame: 0, frameLabel: 'Frame 1 · Hook',
    ev: [ { tone: 1, who: '@stylewithrhea', title: 'Final look first, then rewind', stat: '2.3× her usual views' } ] },
  { id: 'e2', t: 'Look 2 has no takeaway. Your similar reels with a no-payoff middle got 0.6× your usual likes.', frame: 2, frameLabel: 'Frame 3 · Look 2',
    ev: [ { tone: 3, who: 'Your reel', title: 'Thrift haul under ₹2,000', stat: '0.6× your median likes, with a no-payoff stretch at 0:08' } ] },
  { id: 'e3', t: 'Shares are estimated below your baseline — the ending asks for a comment, not a send.', frame: 4, frameLabel: 'Frame 5 · Ending',
    ev: [ { tone: 0, who: 'Similar posts', title: '1,240 festive styling reels', stat: '“Send to a friend” endings: 1.6× shares' } ] }
];
const DNA = {
  content: [ ['Cluster', 'Festive fashion'], ['Sub-cluster', 'One item, many looks'], ['Context', 'Ganpati · festival week'], ['Characters', 'You, solo, direct to camera'], ['Core tension', 'Can one outfit really work three ways?'] ],
  production: [ ['Format', 'Transformation list (3 looks)'], ['Hook', 'Question + promise'], ['Opening', 'Close-up on fabric detail'], ['Narrative', 'Reveal sequence'], ['Ending', 'Pick-one prompt'], ['POV / camera', 'First person · tripod + handheld'], ['Editing', 'Cuts on the beat'], ['Setting', 'Home, natural light'] ],
  trend: [ ['Topic', 'Ganpati outfits'], ['Velocity', 'Rising · 3.4× week on week'], ['Saturation', 'Medium · 1,240 similar posts in 30 days'], ['Peer performance', 'Median 1.6× their baseline'], ['Audience fit', 'High'], ['Creator fit', 'High'], ['Originality', 'Medium · “3 ways” is a common format'] ]
};
const SIM_STEPS = ['Reading Content DNA', 'Reading Production DNA', 'Checking Trend DNA', 'Comparing with your 48 reels', 'Estimating audience response'];

/* ================= HELPERS ================= */
function lc(s) { return s ? s.charAt(0).toLowerCase() + s.slice(1) : s; }
function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
function trimEnd(s) { return String(s || '').trim().replace(/[.!?…]+$/, ''); }
function fmtT(s) { return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); }
function timesFor(n, timing) {
  const T = { 5: { std: ['0:00 – 0:04', '0:05 – 0:12', '0:13 – 0:20', '0:21 – 0:28', '0:29 – 0:32'], short: ['0:00 – 0:03', '0:04 – 0:08', '0:09 – 0:13', '0:14 – 0:18', '0:19 – 0:21'] },
              4: { std: ['0:00 – 0:04', '0:05 – 0:14', '0:15 – 0:24', '0:25 – 0:30'], short: ['0:00 – 0:03', '0:04 – 0:09', '0:10 – 0:16', '0:17 – 0:20'] } };
  if (T[n]) return T[n][timing] || T[n].std;
  const step = timing === 'short' ? 4 : 6; const out = [];
  for (let i = 0; i < n; i++) out.push(fmtT(i * step + (i ? 1 : 0)) + ' – ' + fmtT((i + 1) * step));
  return out;
}
function detectAnn(line) {
  if (/send|share|tag/i.test(line)) return 'shares';
  if (/save/i.test(line)) return 'saves';
  if (/comment|tell me|which|\?\s*$/i.test(line)) return 'comments';
  return null;
}
function segmentsOf(sc, idea) {
  if (!sc) return [];
  let roles, lines = {}, anns = {};
  const e = sc.edits || {};
  if (sc.own) {
    roles = sc.own.map((_, i) => 'o' + i);
    sc.own.forEach((l, i) => { lines['o' + i] = l; anns['o' + i] = i === 0 ? 'hook' : (i === sc.own.length - 1 ? (detectAnn(l) || 'comments') : (/save|step|tip|how/i.test(l) ? 'saves' : null)); });
  } else if (idea && idea.key === 'g3') {
    roles = G3.roles.slice();
    const base = sc.timing === 'short' ? G3.short : (sc.tone === 'conv' ? G3.conv : G3.versions[sc.verIdx % G3.versions.length]);
    lines = Object.assign({}, base);
    if (sc.hookIdx != null) lines.hook = G3.hooks[sc.hookIdx % G3.hooks.length];
    if (sc.ctaIdx != null) lines.cta = G3.ctas[sc.ctaIdx % G3.ctas.length];
    if (e.e1) lines.hook = G3.editHook;
    if (e.e2) lines.look2 = G3.editLook2;
    if (e.e3) lines.cta = G3.editCta;
    anns = Object.assign({}, G3.anns);
    if (e.e2) anns.look2 = 'saves';
    anns.cta = lines.cta === G3.versions[0].cta ? 'shares' : (detectAnn(lines.cta) || 'shares');
  } else {
    roles = ['hook', 'p1', 'p2', 'cta'];
    const t = trimEnd(idea ? idea.title : 'This idea');
    const v = sc.verIdx || 0;
    lines.hook = GEN.hooks[(sc.hookIdx != null ? sc.hookIdx : v) % 3](t + (/[.!?]$/.test(t) ? '' : '.')).replace('..', '.');
    lines.p1 = GEN.p1[v % 3]; lines.p2 = GEN.p2[v % 3];
    lines.cta = GEN.ctas[(sc.ctaIdx != null ? sc.ctaIdx : v) % 3];
    if (sc.tone === 'conv') { lines.p1 = GEN.conv.p1; lines.p2 = GEN.conv.p2; if (sc.ctaIdx == null) lines.cta = GEN.conv.cta; lines.hook = 'Okay, so — ' + lc(t) + '.'; }
    if (sc.timing === 'short') { lines.p1 = GEN.short.p1; lines.p2 = GEN.short.p2; if (sc.ctaIdx == null) lines.cta = GEN.short.cta; lines.hook = t + '.'; }
    anns = { hook: 'hook', p1: null, p2: 'saves', cta: detectAnn(lines.cta) || 'comments' };
  }
  const ts = timesFor(roles.length, sc.timing);
  return roles.map((r, i) => ({ role: r, t: ts[i], line: lines[r], ann: anns[r] || null, tone: TONES[i % TONES.length] }));
}
function framesOf(segs, st, isG3) {
  const n = segs.length;
  return segs.map((sg, i) => {
    let rk = FR[sg.role] ? sg.role : (i === 0 ? 'hook' : (i === n - 1 ? 'cta' : ['look1', 'look2', 'look3'][(i - 1) % 3]));
    const mod = st.frameMods[i] || {};
    const e = (st.script && st.script.edits) || {};
    let base = mod.alt ? FR_ALT[rk] : FR[rk];
    if (rk === 'hook' && e.e1 && !mod.alt && isG3) base = Object.assign({}, base, FR_E1);
    let onScreen = isG3 ? base.onScreen : (sg.line.split(' ').slice(0, 5).join(' ') + (sg.line.split(' ').length > 5 ? '…' : ''));
    if (isG3 && rk === 'look2' && e.e2) onScreen = 'Tip: swap the dupatta for a jacket';
    if (isG3 && rk === 'cta' && e.e3) onScreen = 'Send this to your festive twin';
    return {
      i, rk, t: sg.t, line: sg.line, sketch: base.sketch,
      instr: mod.easy ? EASY[rk] : (isG3 || mod.alt ? base.instr : GEN_INSTR[rk]),
      shot: mod.easy ? 'One take · phone propped on a shelf' : base.shot,
      trans: TRANSITIONS[(base.trans + (mod.trans || 0)) % TRANSITIONS.length],
      onScreen
    };
  });
}
function genIdeas(text, opp) {
  const t = text.toLowerCase();
  let list;
  if (/budget|cheap|afford|under|₹|rupee|price|cost/.test(t)) list = IDEA_BANK.budget;
  else if (/kid|child|niece|nephew|family|mom|mother|sister|cousin/.test(t)) list = IDEA_BANK.family;
  else if (/prep|decor|pooja|puja|morning|routine|bag|mandap/.test(t)) list = IDEA_BANK.prep;
  else if (/home|quick|own|wardrobe|easy|simple|already|fast/.test(t)) list = IDEA_BANK.home;
  else {
    const x = trimEnd(text);
    list = [ { title: cap(x) + ' — in three quick looks.', why: 'Your idea, in your best-performing format.' },
             { title: 'I tried ' + lc(x) + ' for ' + opp.fest + '. Here’s how it went.', why: 'Story framing tends to lift comments for you.' },
             { title: cap(x) + ': what I planned vs what actually happened.', why: 'Expectation vs reality adds tension.' } ];
  }
  const stamp = Date.now();
  return list.map((l, i) => ({ id: 'u' + stamp + i, title: l.title, why: l.why, desc: 'Built from your note “' + trimEnd(text) + '” within the ' + opp.short.toLowerCase() + ' opportunity.' }));
}
const NO_OPP = { id: null, fest: 'the festival', short: 'Your own idea', ideas: [] };
function freshStudio(oppId) {
  const o = OPPS.find(x => x.id === oppId) || null;
  const tags = {}; HASHTAGS.forEach((h, i) => { tags[h.t] = i < 5; });
  return { oppId: o ? o.id : null, stage: 'ideas', maxStep: 0, rounds: o ? [{ prompt: null, ideas: o.ideas }] : [], pick: null, idea: null, pickOpp: false, tagNudge: null,
    script: null, scriptLoading: false, exchange: null, openAnn: null, ownOpen: false, ownText: '',
    frame: 0, frameMods: {}, sbLoading: false, sbNote: null, busyFrame: null,
    capSet: 'base', capIdx: 1, capNote: null, tags };
}
function newScript() { return { verIdx: 0, hookIdx: null, ctaIdx: null, tone: null, timing: 'std', v: 1, edits: {}, own: null }; }
function applyScriptRequest(sc0, text) {
  const t = text.toLowerCase(); const sc = Object.assign({}, sc0, { edits: Object.assign({}, sc0.edits) }); let reply;
  if (sc.own) {
    if (/hook|open|start|first/.test(t)) { sc.own = sc.own.slice(); sc.own[0] = G3.hooks[(sc.v) % 3]; reply = 'Swapped in a stronger opening line. Your other lines are unchanged.'; }
    else if (/end|cta|last|share|save|comment/.test(t)) { sc.own = sc.own.slice(); sc.own[sc.own.length - 1] = G3.ctas[(sc.v) % 3]; reply = 'Rewrote your last line as a clearer call to action.'; }
    else if (/short|trim|tight|faster|20/.test(t)) { sc.timing = 'short'; reply = 'Tightened the timing — each beat now gets about 4 seconds.'; }
    else { reply = 'I’ve kept your lines as written. Try asking for a new hook, a different ending, or a shorter cut.'; }
  } else if (/hook|open|start|first line|punch|attention/.test(t)) { sc.hookIdx = sc.hookIdx == null ? 0 : sc.hookIdx + 1; reply = 'Rewrote the hook to open on a stronger promise. The rest of the script is unchanged.'; }
  else if (/short|trim|tight|faster|20 ?s|20 sec|cut it/.test(t)) { sc.timing = 'short'; sc.tone = null; reply = 'Cut it down to about 20 seconds — same structure, fewer words.'; }
  else if (/long|expand|more detail|slower|detail/.test(t)) { sc.timing = 'std'; reply = 'Expanded back to ~30 seconds so each beat gets room to breathe.'; }
  else if (/convers|natural|casual|tone|friendly|human|me/.test(t)) { sc.tone = 'conv'; sc.timing = 'std'; reply = 'Rewrote it to sound like you’re talking to a friend — closer to how you speak in your top reels.'; }
  else if (/save/.test(t)) { sc.ctaIdx = 1; reply = 'Changed the ending to a save prompt. Saves aren’t public, so Curo can’t measure them; it will track likes and shares instead.'; }
  else if (/share|send|friend/.test(t)) { sc.ctaIdx = 2; reply = 'Changed the ending to a send-to-a-friend prompt. Curo now associates it with shares.'; }
  else if (/end|cta|call to action|outro|last|comment/.test(t)) { sc.ctaIdx = sc.ctaIdx == null ? 0 : sc.ctaIdx + 1; reply = 'Changed the ending — the behaviour label has been updated to match.'; }
  else { sc.verIdx = (sc.verIdx || 0) + 1; sc.hookIdx = null; sc.ctaIdx = null; sc.tone = null; reply = 'Here’s a new take on the same idea, using your note as direction.'; }
  sc.v = (sc.v || 1) + 1;
  return { sc, reply };
}

/* ================= COMPONENT ================= */
class Component extends DCLogic {
  constructor(props) {
    super(props);
    this.timers = [];
    const seed = freshStudio('mistakes'); const m2 = OPPS[2].ideas[1];
    Object.assign(seed, { idea: m2, pick: m2, script: newScript(), stage: 'script', maxStep: 1 });
    this.state = {
      tab: 'home', homeView: 'home', reelIdx: 0, oppId: 'ganpati', saved: { budget: true }, overlay: null,
      drafts: [{ id: 'd-' + m2.id, snapshot: seed, savedAt: 'Yesterday' }],
      studio: freshStudio(null),
      sim: { view: 'intro', source: 'studio', paste: '', audience: 'both', pending: {}, runs: 0, prevScore: null, step: 0, dnaTab: 'content', chat: [], typing: false, openEv: {}, uploaded: false, uploading: false, linked: true },
      toast: null
    };
  }
  componentWillUnmount() { this.timers.forEach(clearTimeout); }
  later(ms, fn) { const id = setTimeout(fn, ms); this.timers.push(id); return id; }
  S(patch) { this.setState(s => ({ studio: Object.assign({}, s.studio, typeof patch === 'function' ? patch(s.studio) : patch) })); }
  M(patch) { this.setState(s => ({ sim: Object.assign({}, s.sim, typeof patch === 'function' ? patch(s.sim) : patch) })); }
  toastMsg(msg) { this.setState({ toast: msg }); if (this.toastT) clearTimeout(this.toastT); this.toastT = this.later(2800, () => this.setState({ toast: null })); }
  top() { this.later(0, () => { if (this.scrollEl) this.scrollEl.scrollTop = 0; }); }
  bottom() { this.later(80, () => { if (this.scrollEl) this.scrollEl.scrollTo({ top: this.scrollEl.scrollHeight, behavior: 'smooth' }); }); }

  /* refs */
  setScroll = (el) => { this.scrollEl = el; };
  setReelEl = (el) => { this.reelEl = el; if (el) { el.scrollLeft = this.state.reelIdx * 182; } };
  setOppEl = (el) => { this.oppEl = el; if (el) { const i = Math.max(0, OPPS.findIndex(o => o.id === this.state.oppId)); el.scrollLeft = i * 390; } };
  setSbEl = (el) => { this.sbEl = el; if (el) { el.scrollLeft = this.state.studio.frame * 250; } };

  /* nav */
  onNav = (tab) => {
    const s = this.state;
    if (tab === s.tab) { this.setState(tab === 'home' ? { homeView: 'home', overlay: null } : { overlay: null }); this.top(); return; }
    this.setState({ tab, overlay: null }); this.top();
  };

  /* home */
  onReelScroll = (e) => { const el = e.currentTarget; const i = Math.round(el.scrollLeft / 182); if (i !== this.state.reelIdx && i >= 0 && i < REELS.length) this.setState({ reelIdx: i }); };
  goReel = (i) => { this.setState({ reelIdx: i }); if (this.reelEl) this.reelEl.scrollTo({ left: i * 182, behavior: 'smooth' }); };
  onOppScroll = (e) => { const i = Math.round(e.currentTarget.scrollLeft / 390); const o = OPPS[i]; if (o && o.id !== this.state.oppId) this.setState({ oppId: o.id }); };
  goOpp = (i) => { this.setState({ oppId: OPPS[i].id }); if (this.oppEl) this.oppEl.scrollTo({ left: i * 390, behavior: 'smooth' }); };
  openSaved = () => { this.setState({ overlay: 'saved' }); this.top(); };
  closeSaved = () => { this.setState({ overlay: null }); this.top(); };
  openSavedOpp = (id) => { this.setState({ overlay: null, tab: 'home', homeView: 'opportunity', oppId: id }); this.top(); };
  unsaveOpp = (id) => { this.setState(s => ({ saved: Object.assign({}, s.saved, { [id]: false }) })); this.toastMsg('Removed from saved.'); };
  openDraft = (d) => { this.setState({ overlay: null, tab: 'studio', studio: JSON.parse(JSON.stringify(d.snapshot)) }); this.top(); };
  toggleTag = (t) => {
    const st = this.state.studio; const on = !!st.tags[t]; const count = Object.keys(st.tags).filter(k => st.tags[k]).length;
    if (!on && count >= 5) { this.toastMsg('You can pick up to 5 hashtags. Remove one to add another.'); this.S({ tagNudge: t }); this.later(500, () => this.S({ tagNudge: null })); return; }
    this.S(x => ({ tags: Object.assign({}, x.tags, { [t]: !on }) }));
  };
  openInsights = (i) => { this.setState({ homeView: 'insights', reelIdx: i }); this.top(); };
  openCurrentInsights = () => this.openInsights(this.state.reelIdx);
  goHomeRoot = () => { this.setState({ homeView: 'home' }); this.top(); };
  openOpp = (id) => { this.setState({ homeView: 'opportunity', oppId: id }); this.top(); };
  toggleSaveOpp = () => { const id = this.state.oppId; const on = !this.state.saved[id]; this.setState(s => ({ saved: Object.assign({}, s.saved, { [id]: on }) })); this.toastMsg(on ? 'Saved. Find it under Saved at the top of Home, Studio or Simulator.' : 'Removed from saved.'); };
  openInStudio = () => { this.setState({ tab: 'studio', studio: freshStudio(this.state.oppId) }); this.top(); };

  /* studio: ideas */
  togglePickOpp = () => this.S(st => ({ pickOpp: !st.pickOpp }));
  chooseStudioOpp = (id) => { this.setState({ studio: freshStudio(id), oppId: id }); };
  pickIdea = (idea) => this.S({ pick: idea });
  continueIdea = () => {
    const st = this.state.studio; if (!st.pick) return;
    const changed = !st.idea || st.idea.id !== st.pick.id;
    this.S(changed ? { idea: st.pick, stage: 'idea', maxStep: 1, script: null, exchange: null, frameMods: {}, frame: 0, ownOpen: false } : { stage: st.script ? 'script' : 'idea', maxStep: Math.max(st.maxStep, 1) });
    this.top();
  };
  sendIdeas = (text) => {
    const st = this.state.studio; const opp = OPPS.find(o => o.id === st.oppId) || NO_OPP;
    const idx = st.rounds.length;
    this.S({ rounds: st.rounds.concat([{ prompt: text, ideas: null }]), pick: null });
    this.bottom();
    this.later(950, () => { this.S(s => ({ rounds: s.rounds.map((r, i) => i === idx ? { prompt: r.prompt, ideas: genIdeas(text, opp) } : r) })); this.bottom(); });
  };
  backToIdeas = () => { this.S({ stage: 'ideas' }); this.top(); };
  toggleOwn = () => this.S(st => ({ ownOpen: !st.ownOpen }));
  onOwnText = (e) => this.S({ ownText: e.target.value });
  useOwn = () => {
    const lines = this.state.studio.ownText.split('\n').map(x => x.trim()).filter(Boolean).slice(0, 8);
    if (!lines.length) return;
    const sc = newScript(); sc.own = lines;
    this.S(st => ({ script: sc, stage: 'script', maxStep: Math.max(st.maxStep, 1), exchange: { user: null, curo: 'I’ve timed your script and marked the lines Curo associates with specific audience behaviours. Ask below to change any part.' }, openAnn: null, frameMods: {} }));
    this.top();
  };

  /* studio: script */
  generateScript = (text) => {
    const st = this.state.studio; if (!st.idea) return;
    this.S({ stage: 'script', maxStep: Math.max(st.maxStep, 1), scriptLoading: true, openAnn: null, frameMods: {} });
    this.top();
    this.later(1150, () => {
      let sc = newScript(); let exchange = null;
      if (text) { const r = applyScriptRequest(sc, text); sc = r.sc; sc.v = 1; exchange = { user: text, curo: 'Generated with your direction in mind. ' + r.reply }; }
      this.S({ script: sc, scriptLoading: false, exchange });
    });
  };
  generateScriptBtn = () => this.generateScript(null);
  regenerate = () => {
    const st = this.state.studio; if (!st.script) return this.generateScript(null);
    this.S({ scriptLoading: true, openAnn: null });
    this.later(950, () => this.S(s => {
      const sc = Object.assign({}, s.script, { verIdx: (s.script.verIdx || 0) + 1, hookIdx: null, ctaIdx: null, tone: null, timing: 'std', v: (s.script.v || 1) + 1, own: null });
      return { script: sc, scriptLoading: false, exchange: { user: null, curo: 'Regenerated the full script. Same idea, a different way in.' } };
    }));
  };
  scriptSend = (text) => {
    const st = this.state.studio; if (!st.script) return this.generateScript(text);
    this.S({ scriptLoading: true, openAnn: null, exchange: { user: text, curo: 'Working on it…' } });
    this.later(900, () => this.S(s => { const r = applyScriptRequest(s.script, text); return { script: r.sc, scriptLoading: false, exchange: { user: text, curo: r.reply } }; }));
  };
  toggleAnn = (i) => this.S(st => ({ openAnn: st.openAnn === i ? null : i }));

  /* studio: storyboard */
  ensureScript() {
    this.S(st => {
      if (st.script && st.idea) return {};
      const opp = OPPS.find(o => o.id === st.oppId) || OPPS[0];
      return { script: st.script || newScript(), idea: st.idea || st.pick || opp.ideas[0], maxStep: Math.max(st.maxStep, 1) };
    });
  }
  toStoryboard = () => {
    this.ensureScript();
    this.S(st => ({ stage: 'storyboard', maxStep: Math.max(st.maxStep, 2), sbLoading: true, frame: 0, sbNote: null }));
    this.top();
    this.later(950, () => this.S({ sbLoading: false }));
  };
  onSbScroll = (e) => { const i = Math.round(e.currentTarget.scrollLeft / 250); const st = this.state.studio; if (i !== st.frame && i >= 0) this.S({ frame: i }); };
  goFrame = (i) => { this.S({ frame: i }); if (this.sbEl) this.sbEl.scrollTo({ left: i * 250, behavior: 'smooth' }); };
  sbSend = (text) => {
    const st = this.state.studio; const t = text.toLowerCase(); const i = st.frame;
    const mods = Object.assign({}, st.frameMods); const m = Object.assign({}, mods[i] || {}); let reply; let target = i; let scriptPatch = null;
    if (/easy|easier|simple|simpl|alone|myself|tripod/.test(t)) { m.easy = true; reply = 'Frame ' + (i + 1) + ' is now a single take with your phone propped up — no tripod or second person needed.'; mods[i] = m; }
    else if (/transition|cut|edit/.test(t)) { m.trans = (m.trans || 0) + 1; mods[i] = m; reply = 'Changed the transition into frame ' + (i + 1) + '.'; }
    else if (/opening|intro|first|start/.test(t)) { const m0 = Object.assign({}, mods[0] || {}); m0.alt = !m0.alt; mods[0] = m0; target = 0; reply = 'Swapped the opening shot. Frame 1 now ' + (m0.alt ? 'starts top-down on the outfit laid flat.' : 'starts on the close-up again.'); }
    else if (/pac|faster|slower|tighter|quick/.test(t)) { scriptPatch = Object.assign({}, st.script, { timing: st.script.timing === 'short' ? 'std' : 'short' }); reply = scriptPatch.timing === 'short' ? 'Tightened the pacing — the reel now runs about 21 seconds. Script timings updated too.' : 'Relaxed the pacing back to ~32 seconds.'; }
    else if (/natural|convers|casual/.test(t)) { scriptPatch = Object.assign({}, st.script, { tone: 'conv', timing: 'std' }); reply = 'Lines now sound more natural. Shots stay the same; spoken lines updated across frames.'; }
    else { m.alt = !m.alt; mods[i] = m; reply = 'Here’s a different shot for frame ' + (i + 1) + '.'; }
    const patch = { frameMods: mods, sbNote: { user: text, curo: reply }, busyFrame: target, frame: target };
    if (scriptPatch) patch.script = scriptPatch;
    this.S(patch);
    if (this.sbEl) this.sbEl.scrollTo({ left: target * 250, behavior: 'smooth' });
    this.later(700, () => this.S({ busyFrame: null }));
  };

  /* studio: caption + final */
  toCaption = () => { this.ensureScript(); this.S(st => ({ stage: 'caption', maxStep: Math.max(st.maxStep, 3) })); this.top(); };
  capSend = (text) => {
    const t = text.toLowerCase(); let set, reply;
    if (/short|brief|less/.test(t)) { set = 'short'; reply = 'Shorter options — each fits before Instagram’s “more” cut-off.'; }
    else if (/fun|play|witty|humou?r/.test(t)) { set = 'playful'; reply = 'More playful options, closer to the tone of your top comments.'; }
    else if (/question|ask|comment/.test(t)) { set = 'question'; reply = 'Each option now ends on a question, to invite comments.'; }
    else { const order = ['base', 'short', 'playful', 'question']; set = order[(order.indexOf(this.state.studio.capSet) + 1) % 4]; reply = 'Here are three new captions based on that.'; }
    this.S({ capSet: set, capIdx: 0, capNote: { user: text, curo: reply } });
  };
  toFinal = () => { this.S(st => ({ stage: 'final', maxStep: 4 })); this.top(); };
  skipToFinal = () => {
    const st = this.state.studio;
    if (!st.idea) { const opp = OPPS.find(o => o.id === st.oppId) || OPPS[0]; this.S({ idea: st.pick || opp.ideas[0] }); }
    this.toFinal();
  };
  editScript = () => { if (this.state.studio.script) { this.S({ stage: 'script' }); this.top(); } else this.generateScript(null); };
  editBoard = () => this.toStoryboard();
  editCaption = () => { this.S({ stage: 'caption' }); this.top(); };
  goStep = (i) => {
    const st = this.state.studio;
    if (i > st.maxStep) return;
    if (i === 0) { this.S({ stage: 'ideas' }); this.top(); return; }
    if (i === 1) { if (st.script) this.S({ stage: 'script' }); else if (st.idea) this.S({ stage: 'idea' }); this.top(); return; }
    this.S({ stage: ['ideas', 'script', 'storyboard', 'caption', 'final'][i], sbLoading: false }); this.top();
  };
  saveDraft = () => {
    const st = this.state.studio; const idea = st.idea || st.pick;
    if (!idea) { this.toastMsg('Pick an idea first, then save your draft.'); return; }
    const snap = JSON.parse(JSON.stringify(Object.assign({}, st, { idea })));
    this.setState(s => ({ drafts: [{ id: 'd-' + idea.id, snapshot: snap, savedAt: 'Just now' }].concat(s.drafts.filter(d => d.id !== 'd-' + idea.id)) }));
    this.toastMsg('Draft saved. Find it under Saved at the top.');
  };

  /* simulator */
  currentScore() {
    const s = this.state; const sim = s.sim; const e = this.simEdits();
    let base = { both: 72, current: 76, new: 64 }[sim.audience];
    if (!this.simLinked()) base -= 3;
    if (s.studio.script && s.studio.script.timing === 'short') base += 1;
    return base + (e.e1 ? 5 : 0) + (e.e2 ? 3 : 0) + (e.e3 ? 4 : 0);
  }
  simEdits() { return this.simLinked() ? ((this.state.studio.script && this.state.studio.script.edits) || {}) : (this.state.sim.localEdits || {}); }
  simLinked() { const st = this.state.studio; return !!(this.state.sim.linked && (st.idea || st.pick)); }
  mockUpload = () => { this.M({ uploading: true, uploaded: false }); this.later(1200, () => this.M({ uploading: false, uploaded: true })); };
  replaceUpload = () => this.M({ uploaded: false });
  toggleLink = () => this.M(sim => ({ linked: !sim.linked }));
  pickStudioSrc = () => this.M({ source: 'studio' });
  pickPasteSrc = () => this.M({ source: 'paste' });
  onPaste = (e) => this.M({ paste: e.target.value });
  setAudience = (a) => this.M({ audience: a });
  runSim = (prevScore) => {
    if (!this.state.sim.uploaded) return;
    if (this.simLinked()) this.ensureScript();
    this.M({ view: 'loading', step: 0, prevScore: prevScore == null ? null : prevScore, pending: {} });
    this.top();
    SIM_STEPS.forEach((_, k) => this.later(430 * (k + 1), () => this.M({ step: k + 1 })));
    this.later(430 * SIM_STEPS.length + 350, () => { this.M(sim => ({ view: 'result', runs: sim.runs + 1 })); this.top(); });
  };
  runSimBtn = () => this.runSim(null);
  simulateDraft = () => { this.setState(s => ({ tab: 'sim', sim: Object.assign({}, s.sim, { source: 'studio', chat: [], openEv: {} }) })); this.later(10, () => this.runSim(null)); };
  toggleEdit = (id) => this.M(sim => ({ pending: Object.assign({}, sim.pending, { [id]: !sim.pending[id] }) }));
  editRerun = () => {
    const s = this.state; const pend = s.sim.pending; if (!Object.keys(pend).some(k => pend[k])) return;
    const prev = this.currentScore();
    const st = s.studio;
    if (!this.simLinked()) {
      const le = Object.assign({}, s.sim.localEdits || {}); Object.keys(pend).forEach(k => { if (pend[k]) le[k] = true; });
      this.M({ localEdits: le }); this.toastMsg('Edits noted. Re-record with these changes, then re-run.'); this.runSim(prev); return;
    }
    const sc = Object.assign({}, st.script || newScript());
    sc.edits = Object.assign({}, sc.edits); Object.keys(pend).forEach(k => { if (pend[k]) sc.edits[k] = true; });
    sc.v = (sc.v || 1) + 1;
    this.S({ script: sc, idea: st.idea || OPPS[0].ideas[0], exchange: { user: null, curo: 'Applied edits from the Simulator. The hook, Look 2 and ending now reflect what you chose.' } });
    this.toastMsg('Edits applied to your Studio script and storyboard.');
    this.runSim(prev);
  };
  toggleSimEv = (key) => this.M(sim => ({ openEv: Object.assign({}, sim.openEv, { [key]: !sim.openEv[key] }) }));
  viewFrame = (i) => {
    if (!this.simLinked()) { this.toastMsg('Link a Studio draft to jump to its storyboard frames.'); return; }
    this.ensureScript();
    this.setState(s => ({ tab: 'studio', studio: Object.assign({}, s.studio, { stage: 'storyboard', maxStep: Math.max(s.studio.maxStep, 2), frame: i, sbLoading: false }) }));
    this.top();
    this.later(120, () => { if (this.sbEl) this.sbEl.scrollTo({ left: i * 250, behavior: 'smooth' }); });
  };
  simSend = (text) => {
    const t = text.toLowerCase(); let a;
    const e = this.simEdits();
    if (/new audience|skip|non-?follower|explore|reach/.test(t)) a = e.e1 ? 'With the reveal-first opening, viewers see the payoff in the first second. Similar reveal-first reels got about 1.3× their usual views.' : 'New-audience viewers decide in about two seconds. Your opening shows a folded outfit, which is close to your average reels; your three best reels showed the finished result first. Edit 1 addresses this.';
    else if (/share|send/.test(t)) a = e.e3 ? 'Your ending now asks for a send, which is what drove shares in similar posts. Share rate is estimated above your baseline.' : 'Your ending asks for a comment, so there’s no reason to send it to anyone. In 1,240 similar posts, endings that named a friend or occasion were shared 1.6× more. Edit 3 changes your ending this way.';
    else if (/best|compare|top/.test(t)) a = 'Compared with “One kurta, five dupattas” (your best reel: 128K views, 940 shares): same “one item, many looks” structure and a similar length. The main difference is the opening — that reel showed all five looks in the first second.';
    else if (/save/.test(t)) a = 'Saves aren’t public, so Curo can’t predict them. Likes are your strongest predicted metric (about 1.2× your baseline) because the looks are easy to recreate.';
    else if (/time|when|post/.test(t)) a = 'Thursday 7–9 PM. Your festive reels posted in that window got 1.4× more views than morning posts.';
    else a = 'Based on your last 48 reels: this draft is strongest on likes and comments and weakest on shares. Ask about any of those for the detail.';
    this.M(sim => ({ chat: sim.chat.concat([{ role: 'user', text }]), typing: true }));
    this.bottom();
    this.later(850, () => { this.M(sim => ({ chat: sim.chat.concat([{ role: 'curo', text: a }]), typing: false })); this.bottom(); });
  };
  backToDrafts = () => { this.M({ view: 'intro' }); this.top(); };
  publish = () => this.toastMsg('Marked as ready to post. Posting to Instagram isn’t connected in this prototype.');
  discard = () => { this.M({ view: 'intro', runs: 0, prevScore: null, chat: [], pending: {}, openEv: {}, localEdits: {}, uploaded: false }); this.toastMsg('Simulation discarded. Your Studio draft is unchanged.'); this.top(); };

  /* composer routing */
  onComposerSend = (text) => {
    const s = this.state;
    if (s.overlay) return;
    if (s.tab === 'studio') {
      const stg = s.studio.stage;
      if (stg === 'ideas') return this.sendIdeas(text);
      if (stg === 'idea') return this.generateScript(text);
      if (stg === 'script') return this.scriptSend(text);
      if (stg === 'storyboard') return this.sbSend(text);
      if (stg === 'caption') return this.capSend(text);
    }
    if (s.tab === 'sim' && s.sim.view === 'result') return this.simSend(text);
  };

  /* ================= RENDER VALUES ================= */
  renderVals() {
    const s = this.state; const st = s.studio; const sim = s.sim;
    const BLUE = '#5B73F2', LAV = '#C3BFF2', PINK = '#F2D4E2', WHITE = '#FFFFFF', GRAY = '#E4E4EC', INK = '#242424', MUTED = 'rgba(36,36,36,.72)';
    const metric = (k, label) => (arr) => {
      const d = arr[1];
      return { label, v: arr[0], d: Math.abs(d), up: d >= 0, down: d < 0, pillBg: d >= 0 ? LAV : PINK,
        iViews: k === 'views', iLikes: k === 'likes', iSaves: k === 'saves', iShares: k === 'shares', iReposts: k === 'reposts', iComments: k === 'comments' };
    };
    const leftOf = (r) => [metric('views', 'Views')(r.m.views), metric('likes', 'Likes')(r.m.likes)];
    const rightOf = (r) => [metric('shares', 'Shares')(r.m.shares), metric('comments', 'Comments')(r.m.comments)];
    const onInsights = s.tab === 'home' && s.homeView === 'insights' && !s.overlay;
    const reels = REELS.map((r, i) => ({ title: r.title, tone: r.tone, duration: r.duration, scale: i === s.reelIdx ? 1 : 0.88, op: i === s.reelIdx ? 1 : 0.5,
      label: i === s.reelIdx ? (onInsights ? r.title : 'View insights for ' + r.title) : 'Show ' + r.title,
      open: () => { if (i !== s.reelIdx) this.goReel(i); else if (!onInsights) this.openInsights(i); } }));
    const reelDots = REELS.map((_, i) => ({ n: i + 1, w: i === s.reelIdx ? 26 : 8, bg: i === s.reelIdx ? BLUE : LAV, go: () => this.goReel(i), pick: () => this.setState({ reelIdx: i }) }));
    const R = REELS[s.reelIdx];
    const PH = ['Testing', 'Peak', 'Plateau', 'Decline'];
    const audIcon = (t) => /comment/i.test(t) ? 'comments' : /share/i.test(t) ? 'shares' : /save/i.test(t) ? 'saves' : /like/i.test(t) ? 'likes' : 'views';
    const ARC = 389.6, ARC_S = 150.8;

    const opp = OPPS.find(o => o.id === s.oppId) || OPPS[0];
    const isSaved = !!s.saved[opp.id];
    const oppD = Object.assign({}, opp, {
      saved: isSaved, saveFill: isSaved ? 'currentColor' : 'none', saveBg: isSaved ? BLUE : WHITE, saveFg: isSaved ? WHITE : INK, saveScale: isSaved ? 1.08 : 1,
      saveLabel: isSaved ? 'Remove from saved' : 'Save for later',
      handles: opp.handles.join(', '), arc: (ARC * (1 - opp.score / 10)).toFixed(1),
      avatars: opp.handles.map((h, i) => ({ i: h.replace('@', '').charAt(0).toUpperCase(), bg: [LAV, PINK, GRAY][i % 3] }))
    });

    /* studio */
    const sOppReal = OPPS.find(o => o.id === st.oppId) || null;
    const sOpp = sOppReal || NO_OPP;
    const idea = st.idea || st.pick || (sOppReal ? sOppReal.ideas[0] : OPPS[0].ideas[0]);
    const oppLabel = sOppReal ? sOppReal.title : 'Your own idea';
    const studioEmpty = !sOppReal && st.rounds.length === 0 && st.stage === 'ideas';
    const isG3 = idea && idea.key === 'g3';
    const segsRaw = segmentsOf(st.script, idea);
    const ANN_BG = { hook: PINK, comments: LAV, saves: GRAY, shares: LAV };
    const segs = segsRaw.map((sg, i) => {
      const a = sg.ann ? ANN[sg.ann] : null; const open = st.openAnn === i; const lead = i === 0;
      return { t: sg.t, line: sg.line, bg: lead ? LAV : GRAY, weight: lead ? 600 : 400, hasAnn: !!a,
        annBg: a ? ANN_BG[sg.ann] : WHITE, annBorder: open ? BLUE : (a && sg.ann === 'shares' ? LAV : 'transparent'),
        isHook: sg.ann === 'hook', isComments: sg.ann === 'comments', isSaves: sg.ann === 'saves', isShares: sg.ann === 'shares',
        annTitle: a ? a.title : '', annDesc: a ? a.desc : '', annLower: a ? a.desc.charAt(0).toLowerCase() + a.desc.slice(1) : '', annEv: a ? a.ev : '', open, evLabel: open ? 'Hide' : 'Why?', delay: i * 70,
        toggle: () => this.toggleAnn(i) };
    });
    const framesRaw = framesOf(segsRaw, st, isG3);
    const fi = Math.min(st.frame, Math.max(framesRaw.length - 1, 0));
    const frames = framesRaw.map((f, i) => {
      const dist = Math.abs(i - fi);
      return Object.assign({}, f, { n: i + 1, scale: dist === 0 ? 1 : 0.9, lift: dist === 0 ? -4 : 0, op: dist === 0 ? 1 : 0.55, border: dist === 0 ? BLUE : GRAY, busy: st.busyFrame === i,
        go: () => this.goFrame(i), open: () => { this.toStoryboard(); this.later(1000, () => this.goFrame(i)); } });
    });
    const curFrame = framesRaw[fi] || { t: '', instr: '', line: '', shot: '', onScreen: '', trans: '' };
    const stageIdx = { ideas: 0, idea: 1, script: 1, storyboard: 2, caption: 3, final: 4 }[st.stage];
    const steps = ['Idea', 'Script', 'Visuals', 'Caption', 'Final'].map((label, i) => {
      const cur = i === stageIdx; const reach = i <= st.maxStep; const done = !cur && (i < st.maxStep || i < stageIdx);
      return { label, n: i + 1, current: cur ? 'step' : 'false', locked: !reach && !cur,
        done, notDone: !done,
        border: cur ? 'none' : (done ? 'none' : '1.5px solid ' + (reach ? LAV : GRAY)),
        bg: cur ? BLUE : (done ? LAV : WHITE), fg: cur ? WHITE : (reach ? INK : MUTED),
        ring: cur ? '0 0 0 6px #FFFFFF, 0 0 0 7px ' + GRAY : '0 0 0 6px #FFFFFF',
        lift: cur ? -6 : 0, scale: cur ? 1.06 : 1,
        color: cur || reach ? INK : MUTED, weight: cur ? 600 : 400, cursor: reach ? 'pointer' : 'default', go: () => this.goStep(i) };
    });
    const studioSub = st.stage === 'storyboard' ? 'Review your storyboard to help you with recording your content.'
      : st.stage === 'caption' ? 'Pick a caption and hashtags that match how you want people to respond.'
      : st.stage === 'final' ? 'Everything for this reel, in one place.'
      : 'Turn opportunity areas into content ideas and start creating.';
    const rounds = st.rounds.map((r) => ({
      hasPrompt: !!r.prompt, prompt: r.prompt, loading: !r.ideas, markClass: r.ideas ? '' : 'spin',
      label: r.prompt ? (r.ideas ? 'Three new directions from your note' : 'Thinking…') : 'Curo suggests',
      ideas: (r.ideas || []).map((it, ii) => {
        const sel = !!(st.pick && st.pick.id === it.id);
        return Object.assign({}, it, { sel, delay: ii * 80, bg: sel ? '#F2D4E2' : WHITE, border: sel ? BLUE : GRAY, lift: sel ? -3 : 0,
          ring: sel ? BLUE : LAV, dot: sel ? BLUE : 'transparent', dotScale: sel ? 1.12 : 1, pick: () => this.pickIdea(it) });
      })
    }));
    const oppChoices = OPPS.map(o => { const on = o.id === st.oppId; return { title: o.title, tag: o.tag, score: o.score, bg: on ? INK : GRAY, fg: on ? WHITE : INK, go: () => this.chooseStudioOpp(o.id) }; });
    const capList = CAPTIONS[st.capSet].map((c, i) => {
      const sel = st.capIdx === i;
      return { t: c.t, why: c.why, sel, delay: i * 70, bg: sel ? PINK : WHITE, border: sel ? BLUE : GRAY, lift: sel ? -3 : 0, chip: sel ? WHITE : GRAY,
        ring: sel ? BLUE : LAV, dot: sel ? BLUE : 'transparent', dotScale: sel ? 1.12 : 1, pick: () => this.S({ capIdx: i }) };
    });
    const tags = HASHTAGS.map(h => { const on = !!st.tags[h.t]; return { t: h.t, kind: h.k, on, bg: on ? INK : GRAY, fg: on ? WHITE : INK, weight: on ? 600 : 400, scale: on ? 1.04 : 1, nudge: st.tagNudge === h.t ? 6 : 0, toggle: () => this.toggleTag(h.t) }; });
    const onTags = HASHTAGS.filter(h => st.tags[h.t]);
    const nNiche = onTags.filter(h => h.k !== 'broad').length;

    /* composer */
    let composer = { placeholder: '', hint: '', voice: '' };
    if (s.tab === 'studio') {
      composer = {
        ideas: studioEmpty ? { placeholder: 'Type your idea or thoughts…', hint: '', voice: 'A festive outfit reel I can shoot at home this weekend' }
          : { placeholder: 'Describe your own idea…', hint: 'Still not sure about any of these? Write your own idea below.', voice: 'Something quick I can shoot at home with what I already own' },
        idea: { placeholder: 'Tell Curo how to write the script…', hint: 'Dump your script idea here if you have something on your mind.', voice: 'Make it sound more like me, more conversational' },
        script: { placeholder: 'Ask Curo to change the script…', hint: 'Dump your script idea here if you have something on your mind.', voice: 'Can you make the hook punchier' },
        storyboard: { placeholder: 'Ask for a different shot…', hint: 'Want a different shot? Keep iterating below.', voice: 'Make this shot easier to record on my own' },
        caption: { placeholder: 'Ask for different captions…', hint: 'Dump your caption idea if you have anything on your mind.', voice: 'Make them more playful' },
        final: composer
      }[st.stage];
    } else if (s.tab === 'sim') {
      composer = { placeholder: 'Ask Curo about this simulation…', hint: 'Ask Curo anything about this simulation.', voice: 'Why might new audiences skip this reel' };
    }
    const showComposer = !s.overlay && ((s.tab === 'studio' && st.stage !== 'final') || (s.tab === 'sim' && sim.view === 'result'));
    const blueDock = !s.overlay && s.tab === 'home' && s.homeView === 'home';

    /* simulator */
    const e = this.simEdits();
    const score = this.currentScore();
    const scoreLabel = score >= 80 ? 'Strong — well above your baseline' : score >= 70 ? 'Likely above your baseline' : score >= 62 ? 'Around your baseline' : 'Below your baseline';
    const linked = this.simLinked();
    const studioIdea = st.idea || st.pick || null;
    const uploadName = (studioIdea ? studioIdea.title.toLowerCase().replace(/[^a-z0-9 ]/g, '').trim().split(/\s+/).slice(0, 4).join('_') : 'my_reel') + '.mp4';
    const draftTitle = linked ? studioIdea.title : uploadName;
    const reachMid = 80 + (e.e1 ? 9 : 0) + (sim.audience === 'new' ? 14 : sim.audience === 'current' ? -12 : 0) + (sim.source === 'paste' ? -10 : 0);
    const mrows = [
      { k: 'Views', pred: reachMid, base: 52, max: 130, val: (reachMid - 12) + 'K – ' + (reachMid + 15) + 'K' },
      { k: 'Like rate', pred: 5.8 + (e.e1 ? 0.2 : 0) + (e.e2 ? 0.3 : 0), base: 4.9, max: 10, unit: '%' },
      { k: 'Comment rate', pred: 0.42, base: 0.21, max: 0.8, unit: '%' },
      { k: 'Share rate', pred: 0.55 + (e.e3 ? 0.35 : 0), base: 0.7, max: 1.5, unit: '%' }
    ];
    const simMetrics = mrows.map(m => {
      const above = m.pred >= m.base; const pct = Math.round((m.pred / m.base - 1) * 100);
      return { k: m.k, val: m.val || (m.pred.toFixed(2).replace(/0$/, '') + m.unit), fill: Math.min(100, m.pred / m.max * 100).toFixed(1), tick: (m.base / m.max * 100).toFixed(1),
        color: above ? BLUE : PINK, deltaColor: above ? LAV : PINK,
        delta: (above ? '+' : '') + pct + '% vs your baseline (' + (m.k === 'Views' ? '52K median' : m.base + '%') + ')' + (above ? '' : ' · below') };
    });
    const weights = { both: [41, 34, 25], current: [38, 52, 10], new: [30, 15, 55] }[sim.audience];
    const personas = [
      { n: 'Festive planners', fit: 86 + (e.e2 ? 4 : 0), d: 'Looking for ready-made looks in the days before the festival.', likely: 'Share' },
      { n: 'Your regulars', fit: 78 + (e.e3 ? 5 : 0), d: 'Followers who reliably comment on your styling reels.', likely: e.e3 ? 'Comment and send' : 'Comment' },
      { n: 'New-audience scrollers', fit: 54 + (e.e1 ? 16 : 0), d: 'People who find you outside your followers. They decide in the first two seconds.', likely: e.e1 ? 'Likely to like' : 'Likely to scroll past' }
    ].map((p, i) => Object.assign(p, { share: weights[i], arc: (ARC_S * (1 - p.fit / 100)).toFixed(1), arcColor: p.fit >= 75 ? BLUE : '#C3BFF2', likelyBg: p.fit >= 75 ? LAV : PINK }));
    const working = WORKING.map((w, i) => { const open = !!sim.openEv['w' + i]; return Object.assign({}, w, { open, rot: open ? 180 : 0, evLabel: open ? 'Hide evidence' : 'See evidence', toggle: () => this.toggleSimEv('w' + i) }); });
    const holding = HOLDING.map((h, i) => {
      const res = !!e[h.id]; const open = !!sim.openEv['h' + i];
      return Object.assign({}, h, { resolved: res, open, evLabel: open ? 'Hide evidence' : 'See evidence', bg: res ? GRAY : WHITE, border: res ? GRAY : PINK, color: res ? MUTED : INK,
        mark: res ? '✓' : '!', markBg: res ? LAV : PINK, markFg: res ? BLUE : INK,
        toggle: () => this.toggleSimEv('h' + i), view: () => this.viewFrame(h.frame) });
    });
    const edits = SIM_EDITS.map(ed => {
      const applied = !!e[ed.id]; const on = !!sim.pending[ed.id]; const checked = applied || on;
      return Object.assign({}, ed, { applied, on, checked, gainLabel: applied ? 'Applied' : '+' + ed.gain + ' est.', gainBg: applied ? WHITE : LAV,
        bg: applied ? GRAY : (on ? '#F2D4E2' : WHITE), border: on && !applied ? BLUE : GRAY, lift: on && !applied ? -3 : 0,
        ring: checked ? BLUE : LAV, dot: checked ? BLUE : 'transparent', dotScale: on && !applied ? 1.1 : 1,
        cursor: applied ? 'default' : 'pointer', toggle: () => { if (!applied) this.toggleEdit(ed.id); } });
    });
    const nPending = SIM_EDITS.filter(ed => sim.pending[ed.id] && !e[ed.id]).length;
    const allApplied = SIM_EDITS.every(ed => e[ed.id]);
    const AUD = [['current', 'Followers'], ['new', 'New audiences'], ['both', 'Both']];
    const audOpts = AUD.map(([id, label]) => { const on = sim.audience === id; return { label, on, bg: on ? INK : GRAY, fg: on ? WHITE : INK, weight: on ? 600 : 400, scale: on ? 1.04 : 1, pick: () => this.setAudience(id) }; });
    const dnaTabs = [['content', 'Content'], ['production', 'Production'], ['trend', 'Trend']].map(([id, label]) => { const on = sim.dnaTab === id; return { label, on, bg: on ? INK : WHITE, fg: on ? WHITE : INK, weight: on ? 600 : 400, scale: on ? 1.04 : 1, pick: () => this.M({ dnaTab: id }) }; });
    let dna = DNA[sim.dnaTab].map(([k, v]) => ({ k, v }));
    if (sim.dnaTab === 'production' && e.e1) dna = dna.map(r => r.k === 'Opening' ? { k: r.k, v: 'Final look first, then rewind' } : r);
    if (sim.dnaTab === 'production' && e.e3) dna = dna.map(r => r.k === 'Ending' ? { k: r.k, v: 'Send-to-a-friend prompt' } : r);
    const simSteps = SIM_STEPS.map((label, k) => { const done = sim.step > k; const cur = sim.step === k; return { label, done, color: done || cur ? INK : MUTED, ring: done || cur ? BLUE : LAV, fill: done ? BLUE : WHITE, scale: cur ? 1.15 : 1, weight: cur ? 600 : 400 }; });
    const simChat = sim.chat.map(c => c.role === 'user'
      ? { text: c.text, justify: 'flex-end', bg: LAV, radius: '22px 22px 6px 22px' }
      : { text: c.text, justify: 'flex-start', bg: GRAY, radius: '22px 22px 22px 6px' });
    const hasScript = !!st.script;
    const ownEmpty = !st.ownText.trim();
    const srcStudio = sim.source === 'studio', srcPaste = sim.source === 'paste';

    /* fixed header + saved + opportunity pages */
    const oppIdx = Math.max(0, OPPS.findIndex(o => o.id === s.oppId));
    let hd = { brand: true };
    if (s.overlay === 'saved') hd = { brand: false, title: 'Saved', back: this.closeSaved, sub: 'Opportunity areas and Studio drafts you kept' };
    else if (s.tab === 'home' && s.homeView === 'insights') hd = { brand: false, title: 'Insights', back: this.goHomeRoot, sub: R.title };
    else if (s.tab === 'home' && s.homeView === 'opportunity') hd = { brand: false, title: 'Opportunity areas', back: this.goHomeRoot, bookmark: true, dots: true };
    const oppDots = OPPS.map((o, i) => ({ n: i + 1, w: i === oppIdx ? 22 : 8, bg: i === oppIdx ? BLUE : WHITE, go: () => this.goOpp(i) }));
    const oppPages = OPPS.map((o, i) => {
      const cur = i === oppIdx;
      return { score: o.score, title: o.title, summary: o.summary, signals: o.signals, more: o.more, compText: o.compText, fit: o.fit,
        handleText: o.handles.join(', '), avatars: o.handles.map((h, j) => ({ i: h.replace('@', '').charAt(0).toUpperCase(), bg: [LAV, PINK, GRAY][j % 3] })),
        scale: cur ? 1 : 0.9, arcNow: cur ? (ARC * (1 - o.score / 10)).toFixed(1) : ARC,
        hasNext: i < OPPS.length - 1, nextTitle: i < OPPS.length - 1 ? OPPS[i + 1].title : '', next: () => this.goOpp(i + 1),
        studio: () => { this.setState({ tab: 'studio', studio: freshStudio(o.id), oppId: o.id, overlay: null }); this.top(); } };
    });
    const savedOpps = OPPS.filter(o => s.saved[o.id]).map(o => ({ title: o.title, tag: o.tag, tagBg: o.tagBg, tagFg: o.tagFg, score: o.score, open: () => this.openSavedOpp(o.id), remove: () => this.unsaveOpp(o.id) }));
    const STAGE_LABEL = { ideas: 'Idea', idea: 'Script', script: 'Script', storyboard: 'Visuals', caption: 'Caption', final: 'Final draft' };
    const savedDrafts = s.drafts.map(d => {
      const sn = d.snapshot; const so = OPPS.find(o => o.id === sn.oppId);
      const di = sn.idea || sn.pick;
      const fr = sn.script ? framesOf(segmentsOf(sn.script, di), sn, di && di.key === 'g3') : [];
      return { title: di ? di.title : 'Untitled draft', opp: so ? so.title : 'Your own idea', stage: STAGE_LABEL[sn.stage] || 'Draft', when: d.savedAt, sketch: fr[0] ? fr[0].sketch : 'closeup', open: () => this.openDraft(d) };
    });
    const savedCount = savedOpps.length + savedDrafts.length;

    return {
      tab: s.tab, setScroll: this.setScroll, onNav: this.onNav, scrollBg: WHITE,
      isSaved: s.overlay === 'saved',
      isHome: !s.overlay && s.tab === 'home' && s.homeView === 'home', isInsights: onInsights, isOpp: !s.overlay && s.tab === 'home' && s.homeView === 'opportunity',
      isStudio: !s.overlay && s.tab === 'studio', isSim: !s.overlay && s.tab === 'sim',
      scrollY: (!s.overlay && s.tab === 'home' && s.homeView === 'opportunity') ? 'hidden' : 'auto',
      hdBrand: hd.brand, hdBack: !hd.brand, hdBackAction: hd.back, hdTitle: hd.title, hdHasBookmark: hd.bookmark, hdNoBookmark: !hd.bookmark,
      hdHasSub: !!hd.sub, hdSub: hd.sub || '', hdHasDots: !!hd.dots, oppDots, oppPos: (oppIdx + 1) + ' of ' + OPPS.length,
      openSaved: this.openSaved, savedCount, hasSavedCount: savedCount > 0,
      savedOpps, savedOppCount: savedOpps.length, noSavedOpps: savedOpps.length === 0,
      savedDrafts, draftCount: savedDrafts.length, noDrafts: savedDrafts.length === 0,
      setOppEl: this.setOppEl, onOppScroll: this.onOppScroll, oppPages,
      curLeft: leftOf(R), curRight: rightOf(R),
      studioEmpty, studioActive: !studioEmpty, hasOpp: !!sOppReal, oppLabel,
      uploadEmpty: !sim.uploaded && !sim.uploading, uploadName, mockUpload: this.mockUpload, replaceUpload: this.replaceUpload, toggleLink: this.toggleLink,
      hasStudioIdea: !!studioIdea, studioIdeaTitle: studioIdea ? studioIdea.title : '', linkTrack: sim.linked ? BLUE : GRAY, linkKnob: sim.linked ? 18 : 0,
      reels, reelDots, setReelEl: this.setReelEl, onReelScroll: this.onReelScroll, reelCmp: R.cmp, reelPos: (s.reelIdx + 1) + ' of ' + REELS.length,
      openCurrentInsights: this.openCurrentInsights, goHomeRoot: this.goHomeRoot,
      opps: OPPS.map(o => ({ tag: o.tag, tagBg: o.tagBg, tagFg: o.tagFg, card: o.card, score: o.score, open: () => this.openOpp(o.id) })), oppCount: OPPS.length,
      insReel: { title: R.title, tone: R.tone, duration: R.duration }, insLeft: leftOf(R), insRight: rightOf(R),
      phase: R.phase,
      phaseTrack: PH.map((label, i) => { const cur = i === R.phase.idx; const past = i < R.phase.idx; return { label, n: i + 1, bg: cur ? BLUE : (past ? LAV : WHITE), fg: cur ? WHITE : INK, ring: cur ? '0 0 0 5px #FFFFFF' : 'none', lift: cur ? -4 : 0, weight: cur ? 600 : 400 }; }),
      audience: R.audience.map((a, i) => { const ic = audIcon(a.t); return Object.assign({}, a, { delay: i * 80, iconBg: [BLUE, LAV, PINK][i % 3], iconFg: i === 0 ? WHITE : INK,
        isComments: ic === 'comments', isShares: ic === 'shares', isSaves: ic === 'saves', isLikes: ic === 'likes', isViews: ic === 'views' }); }),
      topComment: Object.assign({}, R.top, { initial: R.top.handle.charAt(1).toUpperCase() }),
      oppD, toggleSaveOpp: this.toggleSaveOpp, openInStudio: this.openInStudio,

      st, sOpp, idea, studioSub, steps, rounds, oppChoices, togglePickOpp: this.togglePickOpp, pickOppLabel: st.pickOpp ? 'Done' : 'Change',
      stIdeas: st.stage === 'ideas', stIdea: st.stage === 'idea', stScript: st.stage === 'script', stBoard: st.stage === 'storyboard', stCaption: st.stage === 'caption', stFinal: st.stage === 'final',
      hasPick: !!st.pick, continueIdea: this.continueIdea, ideaCtx: 'Your idea · ' + sOpp.short,
      generateScriptBtn: this.generateScriptBtn, toggleOwn: this.toggleOwn, backToIdeas: this.backToIdeas, onOwnText: this.onOwnText, useOwn: this.useOwn, ownEmpty, ownOpacity: ownEmpty ? 0.4 : 1,
      skipToFinal: this.skipToFinal,
      segs, scriptReady: !st.scriptLoading && hasScript, scriptVersion: 'v' + ((st.script && st.script.v) || 1), regenerate: this.regenerate, regenClass: st.scriptLoading ? 'spin' : '',
      hasExchange: !!st.exchange && !st.scriptLoading, exchange: st.exchange ? { hasUser: !!st.exchange.user, user: st.exchange.user, curo: st.exchange.curo } : { hasUser: false },
      toStoryboard: this.toStoryboard,
      frames, frameCount: frames.length, curFrame, sbReady: !st.sbLoading, setSbEl: this.setSbEl, onSbScroll: this.onSbScroll,
      frameDots: frames.map((f, i) => ({ n: i + 1, w: i === fi ? 22 : 8, bg: i === fi ? BLUE : LAV, go: () => this.goFrame(i) })),
      hasSbNote: !!st.sbNote, sbNote: st.sbNote || {}, toCaption: this.toCaption,
      captions: capList, tags, tagSummary: onTags.length + ' picked · ' + nNiche + ' niche, ' + (onTags.length - nNiche) + ' broad',
      hasCapNote: !!st.capNote, capNote: st.capNote || {}, toFinal: this.toFinal,
      noScript: !hasScript, scriptLength: hasScript ? (segsRaw.length ? segsRaw[segsRaw.length - 1].t.split('– ')[1] : '') : 'not started', scriptAction: hasScript ? 'Edit' : 'Generate',
      editScript: this.editScript, editBoard: this.editBoard, editCaption: this.editCaption,
      finalCaption: CAPTIONS[st.capSet][st.capIdx].t, finalTags: onTags.map(h => h.t).join(' '),
      simulateDraft: this.simulateDraft, saveDraft: this.saveDraft,

      composer, showComposer, onComposerSend: this.onComposerSend, composerBusy: st.scriptLoading,

      sim, simIntro: sim.view === 'intro', simLoading: sim.view === 'loading', simResult: sim.view === 'result', simNotResult: sim.view !== 'result',
      simHeadPad: sim.view === 'result' ? 120 : 56,
      srcStudio, srcPaste,
      srcStudioBg: srcStudio ? PINK : WHITE, srcStudioBorder: srcStudio ? BLUE : GRAY, srcStudioLift: srcStudio ? -3 : 0,
      srcPasteBg: srcPaste ? PINK : WHITE, srcPasteBorder: srcPaste ? BLUE : GRAY, srcPasteLift: srcPaste ? -3 : 0,
      pickStudioSrc: this.pickStudioSrc, pickPasteSrc: this.pickPasteSrc, onPaste: this.onPaste,
      draftTitle, draftTitleShort: draftTitle.length > 36 ? draftTitle.slice(0, 34) + '…' : draftTitle,
      draftMeta: hasScript ? ('Script · ' + segsRaw.length + ' frames · caption') : 'Idea only — Curo will draft a script to simulate',
      draftSketch: framesRaw[0] ? framesRaw[0].sketch : 'closeup',
      audOpts, runSimBtn: this.runSimBtn, runDisabled: !sim.uploaded, runOpacity: sim.uploaded ? 1 : 0.45,
      simSteps,
      score, scoreArc: (ARC * (1 - score / 100)).toFixed(1), scoreLabel, hasDelta: sim.prevScore != null && score > sim.prevScore, scoreDelta: '+' + (score - (sim.prevScore || score)),
      scoreSentence: 'Strongest on likes and comments' + (e.e3 ? ' and shares' : '') + '. ' + (e.e1 ? 'The reveal-first opening is the biggest lift.' : 'The slow opening is the main risk.'),
      simMetrics, bestTime: { when: 'Thu, 7–9 PM', why: 'Your festive reels posted in this window got 1.4× more views than morning posts.' },
      working, holding, edits, personas, dnaTabs, dnaRows: dna,
      rerunDisabled: nPending === 0, rerunOpacity: nPending === 0 ? 0.45 : 1,
      rerunLabel: allApplied ? 'All edits applied' : (nPending ? 'Edit & re-run (' + nPending + ')' : 'Select edits to re-run'),
      editRerun: this.editRerun, backToDrafts: this.backToDrafts, publish: this.publish, discard: this.discard,
      simChat, noSimChat: sim.chat.length === 0,

      dockBg: blueDock ? LAV : WHITE, dockPad: blueDock ? 0 : 10,
      hasToast: !!s.toast, toast: s.toast, toastBottom: showComposer ? 190 : 104
    };
  }
}