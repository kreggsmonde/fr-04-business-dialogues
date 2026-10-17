import os, sys, json, time, requests, re
import config

CURRICULUM_CATALOG = [
    [
        "The High-Stakes Negotiation Playbook",
        "Assertive anchoring, polite pushback, and closing multi-million deals"
    ],
    [
        "Executive Presentations That Command the Room",
        "Structure, pacing, persuasive hooks, and handling tough Q&A"
    ],
    [
        "Navigating Office Politics and Difficult Bosses",
        "Diplomatic language, paper trails, and emotional composure"
    ],
    [
        "Pitching Innovations to the Board",
        "Framing risk, highlighting ROI, and building stakeholder consensus"
    ],
    [
        "Salary Negotiations and Career Leaps",
        "Knowing your market value, framing achievements, and counter-offers"
    ],
    [
        "Running High-Impact Strategy Meetings",
        "Agenda discipline, steering discussions, and action item follow-ups"
    ],
    [
        "The Art of Constructive Feedback",
        "Radical candor, growth framing, and performance review dialogues"
    ],
    [
        "Crisis Management and Corporate PR",
        "Acknowledging setbacks, reassuring clients, and executive composure"
    ],
    [
        "Networking at International Conferences",
        "Elevator pitches, building genuine industry alliances, and follow-ups"
    ],
    [
        "Remote Team Leadership and Culture",
        "Overcoming Zoom fatigue, asynchronous clarity, and team morale"
    ]
]

DEFAULT_5_ACTS = [
    ("Act 1: Setting the Foundation", "Opening thoughts and exploring why this theme matters in modern life"),
    ("Act 2: Escaping the Translation Delay", "Practical examples and shifts in mindset to think directly in English"),
    ("Act 3: Everyday Real-World Dialogues", "Roleplay conversations, natural expressions, and active listening reactions"),
    ("Act 4: Handling Awkward Moments & Blunders", "Mind blanks, rescue phrases, and turning small mistakes into humor"),
    ("Act 5: The Daily Fluency Challenge & Key Takeaways", "Actionable speaking exercises and closing thoughts for the week")
]

def load_history_topics() -> list:
    """Reads all past published topics from published_videos.json and history.json to ensure no repeats."""
    past = []
    for fname in ["published_videos.json", "history.json"]:
        fpath = os.path.join(config.BASE_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get("topic"):
                                t = item["topic"].strip()
                                if t not in past:
                                    past.append(t)
            except Exception:
                pass
    return past

def generate_dynamic_topic_ai(past_topics: list, ep_num: int = 1) -> dict:
    """Queries Pollinations AI with past topics history to generate a brand new non-repeating topic."""
    key = config.POLLINATIONS_API_KEY
    if not key:
        return None

    past_sample = past_topics[-30:] if len(past_topics) > 30 else past_topics
    prompt = (
        f"You are the creative executive producer for '{config.CHANNEL_NAME}' {config.LANGUAGE} podcast.\n"
        f"Channel Tagline: {config.TAGLINE}\n"
        f"Niche Style: {config.NICHE_PROMPT}\n"
        f"Language Instruction: {config.SYSTEM_LANGUAGE_INSTRUCTION}\n"
        f"CRITICAL: The topic title, focus overview, and act titles MUST be written ENTIRELY in natural {config.LANGUAGE}!\n\n"
        f"Previously published topics (DO NOT REPEAT OR CLOSELY DUPLICATE ANY OF THESE):\n"
        + json.dumps(past_sample, indent=2, ensure_ascii=False) + "\n\n"
        f"Generate ONE brand new, highly engaging, practical {config.LANGUAGE} episode topic tailored specifically for this channel's style and audience in {config.LANGUAGE}.\n"
        f"Episode #{ep_num}.\n\n"
        f"OUTPUT FORMAT: Return ONLY a valid JSON object matching this schema (no markdown, no other text):\n"
        "{\n"
        '  "id": "ep_' + str(ep_num) + '",\n'
        '  "topic": "Catchy Full Episode Title",\n'
        '  "focus": "Brief overview of what listeners will master today",\n'
        '  "thumbnail_title_1": "FIRST 2-3 WORDS (MAX 16 CHARS)",\n'
        '  "thumbnail_title_2": "SECOND 2-3 WORDS (MAX 16 CHARS)",\n'
        '  "thumbnail_hook": "Catchy Subtitle Hook",\n'
        '  "acts": [\n'
        '    ["Act 1: Title", "Detailed focus description..."],\n'
        '    ["Act 2: Title", "Detailed focus description..."],\n'
        '    ["Act 3: Title", "Detailed focus description..."],\n'
        '    ["Act 4: Title", "Detailed focus description..."],\n'
        '    ["Act 5: Title", "Detailed focus description..."]\n'
        '  ]\n'
        "}"
    )

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": config.POLLINATIONS_MODEL,
        "messages": [
            {"role": "system", "content": "You are a professional podcast producer. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.85
    }

    for attempt in range(3):
        try:
            print(f"[StoryGenerator] Synthesizing dynamic topic via AI (attempt {attempt+1}/3)...")
            resp = requests.post(config.POLLINATIONS_ENDPOINT, json=payload, headers=headers, timeout=25)
            if resp.status_code == 200:
                raw = resp.json()["choices"][0]["message"]["content"].strip()
                if "```" in raw:
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:].strip()
                    raw = raw.split("```")[0].strip()
                data = json.loads(raw)
                topic_val = data.get("topic", "")
                if topic_val and data.get("acts") and len(data["acts"]) >= 4:
                    t_lower = topic_val.lower().strip()
                    past_lowers = [p.lower().strip() for p in past_topics]
                    if t_lower not in past_lowers:
                        print(f"[StoryGenerator] Dynamically generated new topic: '{topic_val}'")
                        return data
        except Exception as e:
            print(f"[StoryGenerator] Dynamic topic attempt {attempt+1} error: {e}")
            time.sleep(1.5)
    return None

def get_next_topic(history: list, custom_topic: str = None, ep_num: int = 1) -> dict:
    if custom_topic:
        words = custom_topic.split()
        mid = len(words) // 2
        t1 = " ".join(words[:mid]) if mid > 0 else words[0]
        t2 = " ".join(words[mid:]) if mid > 0 else "CONVERSATION"
        return {
            "id": "custom",
            "topic": custom_topic,
            "focus": "Engaging conversational discussion on this theme",
            "thumbnail_title_1": t1[:18].upper(),
            "thumbnail_title_2": t2[:18].upper(),
            "thumbnail_hook": "20-Minute English Conversation",
            "acts": DEFAULT_5_ACTS
        }

    past_topics = load_history_topics()

    # 1. Try Dynamic AI topic generation first
    ai_topic = generate_dynamic_topic_ai(past_topics, ep_num=ep_num)
    if ai_topic:
        t1 = ai_topic.get("thumbnail_title_1", "")
        t2 = ai_topic.get("thumbnail_title_2", "")
        if not t1 or not t2:
            words = ai_topic["topic"].split()
            mid = len(words) // 2
            t1 = " ".join(words[:mid])
            t2 = " ".join(words[mid:])
        return {
            "id": ai_topic.get("id", f"ep_{ep_num}"),
            "topic": ai_topic["topic"],
            "focus": ai_topic.get("focus", "Engaging conversational practice"),
            "thumbnail_title_1": t1[:18].upper(),
            "thumbnail_title_2": t2[:18].upper(),
            "thumbnail_hook": ai_topic.get("thumbnail_hook", "20-Minute English Conversation"),
            "acts": ai_topic.get("acts", DEFAULT_5_ACTS)
        }

    # 2. Fallback: Search CURRICULUM_CATALOG for unvisited topic
    past_lowers = [p.lower().strip() for p in past_topics]
    for idx, (title, focus) in enumerate(CURRICULUM_CATALOG):
        if title.lower().strip() not in past_lowers:
            print(f"[StoryGenerator] Selected unvisited curriculum topic: '{title}'")
            words = title.split()
            mid = len(words) // 2
            t1 = " ".join(words[:mid])
            t2 = " ".join(words[mid:])
            return {
                "id": f"ep_{ep_num}",
                "topic": title,
                "focus": focus,
                "thumbnail_title_1": t1[:18].upper(),
                "thumbnail_title_2": t2[:18].upper(),
                "thumbnail_hook": "20-Minute English Conversation",
                "acts": DEFAULT_5_ACTS
            }

    # 3. If all catalog topics used, create advanced cycle variation
    cycle = (ep_num - 1) // len(CURRICULUM_CATALOG) + 1
    cat_idx = (ep_num - 1) % len(CURRICULUM_CATALOG)
    base_title, base_focus = CURRICULUM_CATALOG[cat_idx]
    title = f"{base_title}: Part {cycle} - Advanced Fluency"
    words = title.split()
    mid = len(words) // 2
    t1 = " ".join(words[:mid])
    t2 = " ".join(words[mid:])
    return {
        "id": f"ep_{ep_num}",
        "topic": title,
        "focus": f"Advanced depth on {base_focus}",
        "thumbnail_title_1": t1[:18].upper(),
        "thumbnail_title_2": t2[:18].upper(),
        "thumbnail_hook": f"Masterclass Series Part {cycle}",
        "acts": DEFAULT_5_ACTS
    }

def generate_curated_fallback_act(act_idx: int, act_title: str, topic: str, target_turns: int = 40) -> list:
    is_solo = getattr(config, "IS_SOLO", False)
    h1 = config.HOST1_NAME
    h2 = config.HOST2_NAME
    s1 = config.HOST1_SPEAKER
    s2 = config.HOST2_SPEAKER
    cname = config.CHANNEL_NAME

    # 5 Distinct Content Libraries for SOLO host (Solace English Lounge)
    solo_act_scripts = [
        # Act 1: Mindful Welcome & Setting the Calm Foundation
        [
            f"Welcome to {cname}. Take a gentle, deep breath as we settle in today.",
            f"Our journey today is all about {topic}.",
            "In our busy, fast-paced world, taking quiet time for English is a true gift.",
            "When you listen to calm, measured speech, your nervous system naturally relaxes.",
            "You do not need to analyze every single grammar rule as we speak.",
            "Instead, allow the natural melody and rhythm of English to wash over you.",
            "Notice how words connect smoothly, like gentle waves upon a quiet shore.",
            "Let any tension leave your shoulders as you listen to my voice.",
            "Listening is not an exam; it is a peaceful friendship with language.",
            "When you sit comfortably with English, words begin to feel like old friends.",
            "Take your time with every idea we share in this peaceful space.",
            "There is nowhere else you need to rush to right now.",
            "You are giving yourself the gift of calm, focused attention.",
            "Think about how you started your day this morning.",
            "Did you wake up in a hurry, or did you give yourself a moment to breathe?",
            "A calm morning sets the tone for everything that follows throughout your day.",
            "As we begin, notice the quiet stillness around you.",
            "English can be your sanctuary, a calm retreat from a noisy world.",
            "Let us explore this beautiful theme together, step by peaceful step.",
            "You are doing wonderfully, simply by being here and listening.",
            "Each quiet breath creates more space for natural understanding.",
            "When we rush, we miss the delicate beauty of simple thoughts.",
            "Language is meant to express who you are, not to cause you stress.",
            "Today is a new opportunity to feel at peace with your English voice.",
            "Let the words flow through you with ease and serenity.",
            "Notice the gentle cadence of every phrase as it settles into your mind.",
            "Confidence is born out of quiet familiarity, not aggressive memorization.",
            "As we reflect on our theme, feel how accessible these expressions truly are.",
            "You do not need rare or complicated words to express profound meaning.",
            "The simplest English spoken with calm presence carries the greatest power.",
            "Feel the comfort of this quiet studio space embracing your thoughts.",
            "Let us carry this deep sense of calm into our next reflection."
        ],
        # Act 2: Escaping the Translation Delay & Finding Sensory Flow
        [
            "As we move into our second chapter, let us explore the art of quiet thinking.",
            "So many learners feel exhausted because they translate words in their heads first.",
            "That constant translation creates delay, hesitation, and unnecessary fatigue.",
            "The secret to true fluency is not a faster mental dictionary.",
            "It is learning to connect English words directly to sensory experiences.",
            "When you see soft sunlight filtering through a window, do not translate.",
            "Simply feel the warmth on your hands and think: morning light.",
            "When you hold a warm cup of tea, notice the aroma and think: comforting warmth.",
            "Direct sensory connection bypasses the analytical mind completely.",
            "It connects your voice directly to what you see, feel, and experience.",
            "Let us practice this gentle awareness right now in this quiet moment.",
            "Look around the room where you are listening to me.",
            "Notice three simple objects: a wooden desk, a quiet window, a soft shadow.",
            "Feel how natural that was when you did not overthink the words.",
            "You do not need complicated vocabulary to express profound presence.",
            "Simplicity is the truest elegance in spoken English.",
            "When your mind is still, the right words arise naturally when needed.",
            "Trust that the English you have learned is already resting quietly inside you.",
            "It does not need to be forced to the surface; it flows when you relax.",
            "Give yourself permission to pause before speaking.",
            "A peaceful pause is a sign of composure and inner strength.",
            "Native speakers use pauses all the time to gather their thoughts.",
            "Silence in conversation is not empty; it is full of understanding.",
            "Embrace the quiet pauses between sentences with complete confidence.",
            "You are learning to think, breathe, and live in English.",
            "When you let go of the hurry, conversational flow takes over naturally.",
            "Feel the relief of no longer racing against an imaginary clock.",
            "Speaking directly from sensory impressions brings vibrant life to your voice.",
            "Each thought connects smoothly with the next, without resistance.",
            "Your mind is capable of incredible adaptation when treated with patience.",
            "Rest in this awareness as we deepen our journey today."
        ],
        # Act 3: Everyday Real-World Dialogues & Gentle Expressions
        [
            "In our third chapter, let us explore comforting phrases for everyday conversation.",
            "When someone asks you a question, you never need to rush to reply.",
            "You can use warm, thoughtful bridge phrases that buy you peaceful seconds.",
            "For example, you might say: 'That is a wonderful question to consider.'",
            "Or gently: 'Let me reflect on that for a brief moment.'",
            "Notice how graceful and composed those expressions sound.",
            "They give your mind five peaceful seconds to find the right words.",
            "Another lovely phrase to keep close is: 'I understand what you mean.'",
            "It shows deep empathy and active listening without needing complex speech.",
            "When sharing an opinion, you can softly begin: 'In my experience...'",
            "Or you might say: 'It feels to me that small things matter most.'",
            "These gentle openings invite warmth and connection rather than debate.",
            "They create an open door between you and the person speaking with you.",
            "Repeat these comforting expressions softly under your breath as you listen.",
            "Feel the cadence of the syllables across your lips.",
            "English is a music, and you are tuning your ear to its harmony.",
            "Every expression you welcome today becomes part of your natural voice.",
            "Notice how calm your breathing feels as you practice.",
            "Speaking English can feel as natural as having tea with a dear friend.",
            "Carry these gentle bridges with you into your daily interactions.",
            "They will protect your peace whenever you speak with others.",
            "You do not have to perform; you only need to connect.",
            "Genuine human connection is the true purpose of every language.",
            "Let your words be gentle, sincere, and unhurried.",
            "You are making steady, beautiful progress every single day.",
            "When speaking with warmth, people lean in to listen with kindness.",
            "Simple expressions like 'Take your time' or 'I hear you' build instant trust.",
            "Never underestimate the quiet power of a friendly, calm tone.",
            "Language becomes a bridge of light between human hearts.",
            "Cherish these tools as you step into the world with confidence."
        ],
        # Act 4: Embracing Imperfection & Handling Mind Blanks Gracefully
        [
            "Now let us talk about something that touches every learner: letting go of perfection.",
            "Have you ever stayed silent because you worried about making a small grammar slip?",
            "We often hold ourselves to an impossible standard that native speakers never meet.",
            "Real everyday conversation is spontaneous, human, and wonderfully imperfect.",
            "When you make a small slip, the conversation does not break down.",
            "If a word escapes your mind, a gentle smile and calm words work magic.",
            "You can simply say: 'Pardon me, the word slipped my mind for a second.'",
            "Or with a light laugh: 'Let me rephrase that thought.'",
            "People always appreciate warmth and honesty far more than rigid perfection.",
            "Vulnerability creates authentic trust and genuine human warmth.",
            "Your accent is a testament to your courage and your unique cultural journey.",
            "Speak with pride in the effort and dedication you have shown.",
            "The purpose of speaking is never to impress; it is always to connect.",
            "When your intention is to connect, fear dissolves into calm curiosity.",
            "Give yourself grace for every stumble and every pause along the way.",
            "Celebrate every sentence you speak with ease and confidence.",
            "True fluency is not having zero mistakes; it is feeling peaceful while speaking.",
            "Like a tree growing through the seasons, your skills grow quietly beneath the surface.",
            "Be patient with your unique timing and your unique rhythm.",
            "Breathe out the pressure to be flawless, and breathe in peaceful self-assurance.",
            "Every mistake you encounter is simply a stepping stone to greater confidence.",
            "Trust the process and honour the dedication you bring to each session.",
            "Your voice deserves to be heard, just as it is right now.",
            "Keep your heart light and your curiosity alive.",
            "Peace and confidence are already yours to claim.",
            "No single blunder defines your communication ability.",
            "Native speakers stumble over their words every single day without shame.",
            "Give yourself the same kindness you would offer to a beloved friend.",
            "Let your self-compassion be the anchor that keeps you steady in conversation."
        ],
        # Act 5: Daily Fluency Challenge & Closing Calm Reflections
        [
            "As we reach the closing chapter of our journey today, let us reflect on our daily takeaway.",
            "Before you return to your day, take this quiet intention with you.",
            "Choose one moment today to speak or think in English with complete peace.",
            "Perhaps while looking out at the sky, or taking a quiet evening walk.",
            "Remind yourself: I do not need to rush; I am growing at my own natural pace.",
            "English is not a mountain to climb in haste; it is a garden to nurture with daily care.",
            "Each minute you spend in calm immersion strengthens your intuitive understanding.",
            "Thank you for sharing this peaceful space with me today at {cname}.",
            "I hope this quiet time has brought calm to your mind and warmth to your speaking.",
            "May your day be filled with gentle thoughts, clear words, and unhurried moments.",
            "Remember that your English journey is a path of joyful personal discovery.",
            "Until we meet again tomorrow, keep listening with an open heart and speaking with peace.",
            "Be kind to yourself, enjoy the quiet moments, and have a truly wonderful day.",
            "Take care, and farewell for now.",
            "Carry this stillness with you as you step forward into your day.",
            "Your voice is growing stronger, calmer, and more authentic every day.",
            "Until our next session at the lounge, stay peaceful, mindful, and inspired."
        ]
    ]

    # 5 Distinct Content Libraries for DUAL host channels
    dual_act_scripts = [
        # Act 1: Opening Chemistry & Theme Setup
        [
            (s1, h1, f"Welcome to {cname}! Today we are breaking down {topic}."),
            (s2, h2, "I am so pumped for this one. It is something people run into every single day."),
            (s1, h1, "Exactly. If you can master this, your everyday conversations become ten times smoother."),
            (s2, h2, "Most people overcomplicate it with dry textbook rules when they should just feel the flow."),
            (s1, h1, "That is why we are here: real conversations, real expressions, and zero fluff."),
            (s2, h2, "Let us set the stage. When you think about this theme, what is the first thing that jumps out?"),
            (s1, h1, "It is that initial moment of hesitation when you want to speak up but hold back."),
            (s2, h2, "Oh, 100%! Everyone feels that knot in their stomach before starting a sentence."),
            (s1, h1, "The secret is having a couple of reliable opening moves that break the ice instantly."),
            (s2, h2, "Like stepping onto a moving escalator: once your foot is on, momentum does the rest."),
            (s1, h1, "Love that analogy. Today we are giving you that exact momentum for your speaking."),
            (s2, h2, "Grab your notebook or just listen closely while you commute or relax."),
            (s1, h1, "Repeat the phrases out loud with us whenever you can to build that muscle memory."),
            (s2, h2, "Because listening trains your ear, but speaking out loud trains your vocal confidence."),
            (s1, h1, "Let us dive into the core concepts right now.")
        ],
        # Act 2: Deep Dive & Core Concept Breakdown
        [
            (s2, h2, f"Moving into Act 2, let us dissect the biggest mindset shift for {topic}."),
            (s1, h1, "The number one issue is translating word-for-word from your native language."),
            (s2, h2, "That delay kills your rhythm and makes you feel like you are falling behind."),
            (s1, h1, "Instead of translating, think in chunks and visual associations."),
            (s2, h2, "Give our listeners an example of how that works in real time."),
            (s1, h1, "Instead of translating 'I want to drink coffee', attach the feeling directly to 'Grab a coffee'."),
            (s2, h2, "Boom! 'Grab a coffee' is a three-word chunk. Your brain fires it as a single unit."),
            (s1, h1, "Precisely. Chunks require zero grammar calculation in the heat of the moment."),
            (s2, h2, "And when you use chunks, you immediately sound more natural and conversational."),
            (s1, h1, "Notice how native speakers string chunks together like Lego blocks."),
            (s2, h2, "They never assemble individual syllables from scratch; they use pre-built phrases."),
            (s1, h1, "Today we want you to collect these blocks and add them to your conversational toolkit."),
            (s2, h2, "The more blocks you have ready, the less you have to overthink under pressure."),
            (s1, h1, "It turns speaking from an academic chore into effortless self-expression."),
            (s2, h2, "Let us look at how these blocks function in real-world scenarios next.")
        ],
        # Act 3: Real-World Scenarios & Situational Dialogues
        [
            (s1, h1, "In Act 3, let us roleplay real situations so you can hear this in action."),
            (s2, h2, "Picture this: you are meeting someone new at an event or coffee shop."),
            (s1, h1, "Instead of asking boring questions like 'What is your job?', try: 'What has been keeping you busy lately?'"),
            (s2, h2, "That is such a gold-standard question! It opens the door to hobbies, projects, or fun stories."),
            (s1, h1, "And when they answer, use active listening responses: 'No way!', 'That sounds wild!', or 'I can imagine.'"),
            (s2, h2, "Those short reactions prove you are actually tuned in, not just waiting for your turn to talk."),
            (s1, h1, "What about when there is a lull or awkward silence? How do you recover?"),
            (s2, h2, "Use a conversational pivot: 'Speaking of that, have you heard about...'"),
            (s1, h1, "Or you can say: 'That actually reminds me of something crazy that happened last week.'"),
            (s2, h2, "Pivots keep the conversational ball rolling smoothly without any awkward friction."),
            (s1, h1, "Notice the rhythm we are using right here: throw the ball, catch it, and bounce it back."),
            (s2, h2, "Conversation is always a game of catch, never a one-person presentation."),
            (s1, h1, "Keep practicing that back-and-forth bounce in your daily interactions."),
            (s2, h2, "It makes speaking feel effortless and genuinely enjoyable for both people.")
        ],
        # Act 4: Common Pitfalls & Rescue Phrases
        [
            (s2, h2, "In Act 4, let us tackle the elephant in the room: mind blanks and conversational slips."),
            (s1, h1, "Every single speaker on Earth forgets words or loses their train of thought."),
            (s2, h2, "The difference between confident speakers and nervous speakers is how they handle the slip."),
            (s1, h1, "Nervous speakers freeze and panic. Confident speakers use rescue phrases with a smile."),
            (s2, h2, "What are your top rescue phrases when the word completely vanishes?"),
            (s1, h1, "I love saying: 'The word is on the tip of my tongue, but you know what I mean!'"),
            (s2, h2, "Or simply: 'Lost my train of thought for a second—where was I?'"),
            (s1, h1, "Everyone relates to that! People will immediately chime in and help you out."),
            (s2, h2, "It actually builds rapport because it shows you are human and comfortable in your skin."),
            (s1, h1, "And stop apologizing for having an accent or making a tiny preposition error."),
            (s2, h2, "An accent just means you have the bravery to speak more than one language!"),
            (s1, h1, "Wear your voice with pride. Focus 100% on connection, not robotic perfection."),
            (s2, h2, "Connection wins every single time. That is the ultimate speaking superpower.")
        ],
        # Act 5: Daily Challenge & Wrap-up
        [
            (s1, h1, f"We have reached Act 5: our key takeaways and your daily fluency challenge for {topic}."),
            (s2, h2, "Time to put what you have absorbed into real practice before today ends."),
            (s1, h1, "Here is your challenge: use at least one phrase or chunk we covered today in a real conversation."),
            (s2, h2, "Even if it is just sending an audio voice note to a friend or talking to yourself in the mirror!"),
            (s1, h1, "Speaking out loud activates the physical motor pathways in your mouth and tongue."),
            (s2, h2, "Consistent small daily reps beat studying three hours on Sunday every single time."),
            (s1, h1, f"Thank you so much for hanging out with us on {cname} today."),
            (s2, h2, "Make sure to subscribe, leave a like, and share this episode with an English-learning friend!"),
            (s1, h1, "Keep listening, stay curious, and keep speaking up with confidence."),
            (s2, h2, "We will see you right back here tomorrow for another masterclass. Peace!"),
            (s1, h1, "Take care and keep shining!")
        ]
    ]

    safe_act_idx = min(act_idx, len(solo_act_scripts) - 1)
    result = []

    if is_solo:
        lines = solo_act_scripts[safe_act_idx]
        for l in lines:
            result.append({"speaker": s1, "name": h1, "text": l})
            if len(result) >= target_turns:
                break
        # If still need more turns for large target_turns, loop with variations
        while len(result) < target_turns:
            for l in lines:
                result.append({"speaker": s1, "name": h1, "text": f"Reflecting further on this, {l[0].lower() + l[1:] if len(l) > 1 else l}"})
                if len(result) >= target_turns:
                    break
    else:
        turns_data = dual_act_scripts[safe_act_idx]
        for spk, nm, txt in turns_data:
            result.append({"speaker": spk, "name": nm, "text": txt})
            if len(result) >= target_turns:
                break
        while len(result) < target_turns:
            for spk, nm, txt in turns_data:
                result.append({"speaker": spk, "name": nm, "text": f"And another key thing is that {txt[0].lower() + txt[1:] if len(txt) > 1 else txt}"})
                if len(result) >= target_turns:
                    break

    return result

def generate_act_ai(act_idx: int, act_title: str, topic_title: str, focus: str, target_turns: int = 40) -> list:
    key = config.POLLINATIONS_API_KEY
    if not key:
        return None

    if act_idx == 0:
        transition_note = "Opening act: Warmly welcome the listener to the episode and introduce today's topic."
    elif act_idx == 1:
        transition_note = "Act 2: CRITICAL - DO NOT say 'welcome' or 'welcome back' or repeat the show name. Continue naturally from Act 1, moving directly into the core concepts."
    elif act_idx == 2:
        transition_note = "Act 3: CRITICAL - DO NOT say 'welcome' or 'welcome back'. Continue seamlessly into real-world scenarios and practical spoken examples."
    elif act_idx == 3:
        transition_note = "Act 4: CRITICAL - DO NOT say 'welcome' or 'welcome back'. Flow naturally into overcoming mistakes, awkward moments, and mind blanks."
    else:
        transition_note = "Act 5 (Closing): CRITICAL - DO NOT say 'welcome' or 'welcome back'. Transition smoothly into the daily practice challenge, final reflections, and closing sign-off."

    if config.IS_SOLO:
        prompt = (
            f"Write an engaging solo host monologue podcast for '{config.CHANNEL_NAME}'.\n"
            f"Host: {config.HOST1_NAME} ({config.HOST1_SPEAKER}).\n"
            f"Format: SOLO FEMALE HOST speaking warmly, soothingly, and directly to the listener (no co-host, no other voices).\n"
            f"Niche: {config.NICHE_PROMPT}.\n"
            f"Topic: {topic_title}\n"
            f"Act {act_idx + 1}: {act_title}\n"
            f"Focus: {focus}\n"
            f"Transition Guidance: {transition_note}\n\n"
            f"REQUIREMENTS:\n"
            f"- Exactly {target_turns} continuous spoken monologue turns exclusively by {config.HOST1_NAME}.\n"
            f"- Each turn should be 12-24 words of gentle, insightful, natural French speech (French native immersion).\n"
            f"- Strictly return valid raw JSON array only:\n"
            f"[\n"
            f'  {{"speaker": "{config.HOST1_SPEAKER}", "name": "{config.HOST1_NAME}", "text": "..."}},\n'
            f'  {{"speaker": "{config.HOST1_SPEAKER}", "name": "{config.HOST1_NAME}", "text": "..."}}\n'
            f"]"
        )
    else:
        prompt = (
            f"Write an engaging dialogue entirely in French for podcast '{config.CHANNEL_NAME}'.\nLanguage instruction: {config.SYSTEM_LANGUAGE_INSTRUCTION}\n"
            f"Hosts: {config.HOST1_NAME} ({config.HOST1_SPEAKER}) and {config.HOST2_NAME} ({config.HOST2_SPEAKER}).\n"
            f"Niche: {config.NICHE_PROMPT}.\n"
            f"Topic: {topic_title}\n"
            f"Act {act_idx + 1}: {act_title}\n"
            f"Focus: {focus}\n"
            f"Transition Guidance: {transition_note}\n\n"
            f"REQUIREMENTS:\n"
            f"- Exactly {target_turns} dialogue turns alternating {config.HOST1_NAME} and {config.HOST2_NAME}.\n"
            f"- Keep each turn natural, clear, and conversational (12-22 words per turn).\n"
            f"- Warm, insightful, friendly chemistry between hosts.\n"
            f"- Strictly return valid raw JSON array only:\n"
            f"[\n"
            f'  {{"speaker": "{config.HOST1_SPEAKER}", "name": "{config.HOST1_NAME}", "text": "..."}},\n'
            f'  {{"speaker": "{config.HOST2_SPEAKER}", "name": "{config.HOST2_NAME}", "text": "..."}}\n'
            f"]"
        )

    try:
        resp = requests.post(
            config.POLLINATIONS_ENDPOINT,
            json={
                "model": config.POLLINATIONS_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a JSON-only API. Return only a raw JSON array of dialogue objects."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.75
            },
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=25
        )
        if resp.status_code == 200:
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:].strip()
                raw = raw.split("```")[0].strip()
            parsed = json.loads(raw)
            min_needed = max(2, min(target_turns, 8))
            if isinstance(parsed, list) and len(parsed) >= min_needed:
                result_turns = []
                for p in parsed:
                    txt = p.get("text", "").strip()
                    if not txt:
                        continue
                    if config.IS_SOLO:
                        spk = config.HOST1_SPEAKER
                        nm = config.HOST1_NAME
                    else:
                        spk = p.get("speaker", config.HOST1_SPEAKER)
                        nm = p.get("name", config.HOST1_NAME)
                    result_turns.append({"speaker": spk, "name": nm, "text": txt})

                # Sanitize repetitive greetings in Acts 2-5
                if act_idx > 0 and result_turns:
                    first_text = result_turns[0]["text"]
                    for prefix in ["welcome back", "welcome to", "hello and welcome back", "hello, dear listener, and welcome back"]:
                        if first_text.lower().startswith(prefix):
                            cleaned = re.sub(r"^(?:welcome back(?:,\s*dear[^,.]*)? to [^.!?]*[.!?]\s*|welcome to [^.!?]*[.!?]\s*|hello[,\s]+(?:dear[^,.]*)?(?:and\s+)?welcome back to [^.!?]*[.!?]\s*)", "", first_text, flags=re.IGNORECASE).strip()
                            if cleaned:
                                result_turns[0]["text"] = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned
                            else:
                                result_turns[0]["text"] = f"Continuing our reflection on {topic_title}, let us explore how this applies directly to our daily thoughts."
                            break

                if len(result_turns) >= target_turns:
                    return result_turns[:target_turns]
                elif len(result_turns) >= min_needed:
                    # Pad seamlessly with unique non-repeating turns from fallback
                    fallback_turns = generate_curated_fallback_act(act_idx, act_title, topic_title, target_turns=target_turns)
                    seen_texts = set(r["text"] for r in result_turns)
                    for ft in fallback_turns:
                        if len(result_turns) >= target_turns:
                            break
                        if ft["text"] not in seen_texts:
                            result_turns.append(ft)
                            seen_texts.add(ft["text"])
                    return result_turns[:target_turns]
    except Exception as e:
        print(f"  [AI Note] Act {act_idx+1} Pollinations call error ({e}), using curated master script.")
    return None

def generate_full_podcast_story(target_minutes: float = 20.0, topic: str = None, ep_num: int = 1) -> dict:
    history = load_history_topics()
    topic_info = get_next_topic(history, custom_topic=topic, ep_num=ep_num)
    selected_topic = topic_info["topic"]
    acts_meta = topic_info.get("acts", DEFAULT_5_ACTS)

    print(f"[StoryGenerator] Episode #{ep_num} Topic: '{selected_topic}'")

    # Target 20 minutes: ~190-200 turns total (~38-40 turns per act)
    turns_per_act = int(max(4, (target_minutes * 60) / (len(acts_meta) * 6.0)))
    if target_minutes <= 1.0:
        turns_per_act = 4
    elif target_minutes <= 3.0:
        turns_per_act = 8

    dialogue = []
    chapters = []

    for act_idx, (act_title, act_focus) in enumerate(acts_meta):
        chapters.append({"title": act_title, "start_turn": len(dialogue)})
        print(f"  [Act {act_idx+1}/5] Generating '{act_title}' ({turns_per_act} turns)...")

        turns = generate_act_ai(act_idx, act_title, selected_topic, act_focus, target_turns=turns_per_act)
        if not turns:
            turns = generate_curated_fallback_act(act_idx, act_title, selected_topic, target_turns=turns_per_act)

        dialogue.extend(turns)

    print(f"[StoryGenerator] Completed {len(dialogue)} total dialogue turns across {len(acts_meta)} acts.")
    return {
        "topic": selected_topic,
        "thumbnail_title_1": topic_info["thumbnail_title_1"],
        "thumbnail_title_2": topic_info["thumbnail_title_2"],
        "thumbnail_hook": topic_info["thumbnail_hook"],
        "chapters": chapters,
        "dialogue": dialogue
    }

def generate_metadata(topic: str, duration_sec: float, chapters: list, ep_num: int = 1) -> dict:
    title = f"{topic} | {config.CHANNEL_NAME} Ép. {ep_num}"
    lines = [
        f"🎙️ Bienvenue sur {config.CHANNEL_NAME} - Épisode #{ep_num} !",
        f"Aujourd'hui, nous explorons : {topic}.",
        "",
        "🕒 CHAPITRES ET HORODATAGES :"
    ]
    for ch in chapters:
        m = int(ch.get("start_time", 0) // 60)
        s = int(ch.get("start_time", 0) % 60)
        lines.append(f"{m:02d}:{s:02d} - {ch['title']}")

    lines.extend([
        "",
        "💡 Détendez-vous, écoutez et plongez au cœur de conversations naturelles en français.",
        "👉 Abonnez-vous à notre page pour de nouveaux épisodes quotidiens !",
        f"#{config.CHANNEL_NAME.replace(' ', '')} #ApprendreLeFrancais #PodcastFrancais #FrancaisNaturel #ImmersionFrancaise"
    ])

    return {
        "title": title[:100],
        "description": "\n".join(lines),
        "tags": ["apprendre le francais", "podcast francais", config.CHANNEL_NAME.lower(), "francais conversation", "ecoute francais"]
    }
