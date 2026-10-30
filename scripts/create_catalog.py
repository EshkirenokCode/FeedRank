"""Original, evergreen demo summaries. No MIND article text is redistributed."""

import json
from pathlib import Path

CONTENT = {
    "science": [
        (
            "A quieter way to watch the night sky",
            "A small observatory can learn a lot by recording the same patch of sky over many nights. Consistent measurements reveal changes that a single image misses.",
            "Start with a stable camera and a clear log of conditions. Compare images taken at the same hour. Clouds, moonlight and sensor temperature can all change a measurement. Repeated observations help separate those effects from a change in the sky.",
        ),
        (
            "What a river sample can tell us",
            "Water carries traces of the landscape it crosses. Simple measurements of temperature, clarity and acidity can help a community understand a local river.",
            "Collect samples from the same locations and record recent rain. One unusual reading is a reason to investigate, rather than proof of a lasting trend. Good records make a small monitoring project useful over time.",
        ),
        (
            "Why soil holds more than roots",
            "Healthy soil is a living network of minerals, fungi and tiny organisms. Its structure influences how a garden stores water and supports plants.",
            "Compare a covered patch with bare ground after rain. Watch how quickly water enters and how long the surface stays damp. Soil changes slowly, so repeat observations across seasons.",
        ),
        (
            "Listening for birds in a city park",
            "An early walk can reveal a surprisingly rich soundscape. A repeatable route makes casual bird listening more useful.",
            "Choose a short route and record what you hear at fixed stops. Weather, time and background noise matter. Avoid disturbing nests and treat uncertain identifications as uncertain.",
        ),
        (
            "A closer look at everyday materials",
            "Paper, glass and metal react differently to heat and moisture. A few careful observations explain why material choice matters in daily objects.",
            "Think about the job an object must do. A reusable container needs a safe seal as well as a durable wall. There is rarely one best material for every use.",
        ),
        (
            "How a weather diary becomes data",
            "A notebook of local weather is a small scientific instrument. A clear method matters more than a long list of readings.",
            "Measure in the same place and at the same hour. Keep the sensor away from direct heat. Record missing readings honestly. A diary helps describe local conditions, but does not replace regional climate analysis.",
        ),
    ],
    "health": [
        (
            "Making room for a daily walk",
            "A short walk can be easier to keep than an ambitious new routine. A familiar route and a regular time reduce the effort of getting started.",
            "Choose a comfortable distance and adjust it to your own needs. A walk can be a chance to notice your neighbourhood, call a friend or simply leave a screen behind. This is a general lifestyle note, not individual medical advice.",
        ),
        (
            "Building a calmer evening routine",
            "A repeatable evening can make the end of a busy day feel less rushed. Small environmental changes are often easier than a strict schedule.",
            "Set aside a place for tomorrow’s essentials. Lower unnecessary noise and leave time for a quiet activity. If sleep problems persist, seek advice from a qualified clinician.",
        ),
        (
            "A useful pause between long meetings",
            "A brief break offers a chance to move, look away from the screen and reset attention. It does not need an elaborate routine.",
            "Stand or change position if comfortable. Look across the room, get some water and check the next meeting’s purpose. Make breaks accessible to colleagues with different mobility needs.",
        ),
        (
            "Cooking a simple lunch ahead",
            "A flexible lunch plan can reduce daily decisions. A grain, some vegetables and a familiar protein source form a useful starting point.",
            "Use ingredients you enjoy and can store safely. Keep chilled food cold and follow package guidance. Adapt meals to allergies and individual dietary needs.",
        ),
        (
            "Designing a desk around comfort",
            "A comfortable workspace leaves room to change position. Screen height, lighting and easy access to frequently used objects all matter.",
            "Try one adjustment at a time and notice how it feels over a full day. An expensive chair cannot replace breaks. Persistent pain deserves professional assessment.",
        ),
        (
            "Keeping a useful habit record",
            "A habit log works best when it is easy to maintain. Recording a small action can reveal patterns without turning every day into a score.",
            "Write down what happened and what made it easier or harder. Review a week at a time. Leave room for illness, travel and ordinary changes in energy.",
        ),
    ],
    "finance": [
        (
            "Reading a household budget clearly",
            "A budget is a view of choices and obligations. Separating regular bills from irregular costs can make the next month easier to understand.",
            "List expected income and necessary costs first. Reserve space for expenses that occur only a few times a year. Estimates are useful when labelled clearly. This is an educational example, not financial advice.",
        ),
        (
            "The hidden cost of a small subscription",
            "Several modest recurring charges can become difficult to track. A periodic review helps connect each payment with a service that is still useful.",
            "Check renewal dates and cancellation terms. Include annual plans in a monthly view. Keep services because they are useful, rather than because cancelling feels inconvenient.",
        ),
        (
            "Why a price comparison needs context",
            "The lowest price can hide different delivery costs, sizes or repair options. A fair comparison starts with the same unit and the same use case.",
            "Compare total cost, expected use and the return policy. A durable item may cost more initially. That does not make it automatically better for every household.",
        ),
        (
            "Making an irregular expense calendar",
            "Annual bills and occasional repairs can disrupt an otherwise steady budget. A calendar makes those costs visible before they arrive.",
            "Start with last year’s known dates. Mark estimates and leave room for uncertainty. Review the calendar when circumstances change, rather than assuming the plan is fixed.",
        ),
        (
            "Understanding a savings goal",
            "A clear goal has an amount, a date and a reason. Those three details make it easier to see whether a plan is realistic.",
            "Break the amount into manageable intervals and consider possible interruptions. Keep emergency needs separate. No particular investment product is recommended here.",
        ),
        (
            "A receipt can be a useful record",
            "A simple record of larger purchases helps with warranties, returns and household planning. It need not become a complicated accounting system.",
            "Store the date, seller and warranty information where you can find them. Avoid keeping unnecessary personal information in shared folders. Review records when the item leaves your household.",
        ),
    ],
    "sports": [
        (
            "What makes a local running route work",
            "A good route balances distance, surface and safe crossings. Familiar loops can make a regular run easier to plan.",
            "Check lighting and access before setting out. Leave room to shorten the route and adapt pace to conditions. A route shared with walkers works best when everyone has space.",
        ),
        (
            "Watching a match beyond the score",
            "Movement away from the ball often explains how a team creates space. Watching one player for a few minutes can reveal that pattern.",
            "Notice where teammates move when possession changes. Compare a sequence that creates an opening with one that stalls. A single match is too small a sample for sweeping conclusions.",
        ),
        (
            "A beginner’s guide to a cycling loop",
            "A short cycling loop gives new riders a manageable way to learn local roads. The return journey matters as much as the outward route.",
            "Check the bike, weather and road rules. Pick a route suited to your confidence and leave time for stops. A helmet and visible clothing are useful parts of preparation.",
        ),
        (
            "Why teams review ordinary plays",
            "A routine sequence can contain a useful lesson about communication. Reviewing a few clear moments is often more useful than replaying every error.",
            "Agree on the question before watching a recording. Describe what happened without assigning motives. Choose one change the team can try in its next practice.",
        ),
        (
            "Finding space for a community game",
            "A shared court or field needs more than a booking. Clear times, simple rules and room for newcomers make a community game easier to join.",
            "Explain the level and equipment needed in advance. Offer a way to rotate fairly. A welcoming game gives people a reason to return without needing a formal league.",
        ),
        (
            "Keeping an honest training log",
            "A useful log records effort and recovery as well as distance or weight. Context can explain why two sessions with the same numbers feel different.",
            "Record only a few measures consistently. Include rest days and note unusual conditions. A log supports reflection; it is not a substitute for qualified coaching or medical care.",
        ),
    ],
    "foodanddrink": [
        (
            "A flexible soup for a quiet evening",
            "Soup is a forgiving way to use a few vegetables and a simple stock. Texture and seasoning can be adjusted near the end.",
            "Cook firm vegetables first, then add softer ingredients. Taste before adding more salt. Cool leftovers promptly and store them according to food safety guidance.",
        ),
        (
            "Getting to know a local market",
            "A market visit can begin with one seasonal ingredient. Asking how a seller uses it often offers a practical starting point.",
            "Walk around before buying. Compare freshness, quantity and how soon you will cook. A small purchase is a good way to try an unfamiliar ingredient without waste.",
        ),
        (
            "A better plan for leftover bread",
            "Bread changes texture before it becomes unusable. Toasts, crumbs and a simple savoury bake each suit a different stage.",
            "Freeze portions you will not use soon. Avoid bread with mould. Label stored portions so that a useful leftover does not become an unknown package.",
        ),
        (
            "Why a recipe is also a sequence",
            "Good cooking instructions coordinate time as well as ingredients. Reading the whole recipe first can prevent a rushed final step.",
            "Find the longest task and start there. Prepare tools and measure ingredients before heating a pan. Note changes for next time instead of relying on memory.",
        ),
        (
            "An easy way to compare coffee",
            "A consistent brewing method makes differences between coffees easier to notice. Change one variable at a time.",
            "Use the same water, cup and amount of coffee. Write a few plain words about aroma and taste. Your own preference is more useful than a complicated tasting vocabulary.",
        ),
        (
            "Making a shared meal easier",
            "A shared meal works best when dietary needs and timing are clear. A modest menu leaves more room for conversation.",
            "Ask about allergies in advance. Choose dishes that can wait a little without losing their texture. Keep a simple option available for guests with different needs.",
        ),
    ],
    "travel": [
        (
            "Seeing a familiar city on foot",
            "A walk through a different neighbourhood can feel like a small journey. A loose theme gives the route a shape without filling every minute.",
            "Look for public gardens, old shopfronts or a river path. Check opening hours before relying on a destination. Leave room to change the route when something catches your attention.",
        ),
        (
            "Packing for a short train journey",
            "A small bag is easier to manage when the essentials are easy to reach. A clear plan for tickets, water and a charger prevents repeated unpacking.",
            "Check luggage rules and keep important documents secure. Pack for the expected weather and a modest delay. Avoid carrying items you are unlikely to use.",
        ),
        (
            "A slower day at a coastal town",
            "A quieter visit can centre on a walk, a local meal and time near the water. Fewer stops leave room to understand a place.",
            "Check tides, access rules and transport before leaving. Respect residents and protected areas. A beach is a shared environment, not simply a backdrop for a photograph.",
        ),
        (
            "Choosing a museum with time to spare",
            "One well-chosen museum can be more memorable than a rushed list. A short visit with a clear interest is often enough.",
            "Choose a room or collection that matters to you. Check accessibility and ticket arrangements. Leave time to sit and look closely at a few objects.",
        ),
        (
            "Keeping a useful travel notebook",
            "A short note about a route or a meal can preserve details that photographs miss. A notebook can also help the next visit.",
            "Record practical details alongside impressions. Keep private addresses and personal documents out of shared notes. Dates help distinguish a useful memory from current advice.",
        ),
        (
            "A weekend closer to home",
            "A nearby destination reduces travel time and makes a short break easier to arrange. Familiar transport can leave more energy for the visit itself.",
            "Choose one main activity and check the return journey. Consider weather alternatives. A good weekend does not need a long distance or an expensive itinerary.",
        ),
    ],
    "news": [
        (
            "How to read a local planning notice",
            "A planning notice describes a proposal and the process for commenting on it. A clear reading separates what is proposed from what is already approved.",
            "Find the address, dates and reference number. Read the actual documents when available. A summary may omit details that matter to a particular neighbour.",
        ),
        (
            "A library as a shared neighbourhood space",
            "Libraries offer room for reading, learning and meeting. Understanding how a branch is used can help a community discuss its future.",
            "Look at access, opening hours and the range of activities. Listen to people who use the space differently. A busy room alone does not describe every form of value.",
        ),
        (
            "Making sense of a public meeting agenda",
            "An agenda reveals which decisions a meeting may address. Reading it ahead of time makes a long discussion easier to follow.",
            "Mark items relevant to you and check whether public comments are invited. Distinguish a discussion item from a final vote. Follow up with the published minutes.",
        ),
        (
            "What a neighbourhood map leaves out",
            "Maps simplify a place. They can show roads clearly while missing steps, shade or a difficult crossing.",
            "Walk a route and compare it with the map. Note access barriers and temporary closures. Local observations can improve a route, but should not expose private information.",
        ),
        (
            "A careful way to compare public claims",
            "A useful comparison begins with the exact claim and its source. Dates and definitions often explain why two figures appear to disagree.",
            "Check whether the figures describe the same place and period. Look for the original document and any later corrections. Keep uncertainty visible when the evidence is incomplete.",
        ),
        (
            "Small repairs in shared public spaces",
            "A broken bench or missing sign can change how a space is used. A clear report makes a small problem easier to locate and address.",
            "Use the appropriate local reporting channel and describe the location precisely. Avoid photographing bystanders unnecessarily. Keep a record of the report without assuming an immediate repair.",
        ),
    ],
    "lifestyle": [
        (
            "A shelf that is easier to use",
            "Storage works when everyday objects are easy to find and return. A modest rearrangement can be more useful than buying more containers.",
            "Start with one shelf and group objects by use. Keep frequently used items within comfortable reach. Leave some empty space so the system can change.",
        ),
        (
            "Making a small room feel calmer",
            "A clear walking path and a few useful surfaces can improve a small room. Light and proportion matter more than filling every corner.",
            "Move one object at a time and notice the effect during daily use. Keep safety and access in mind. A room should work for the people who live in it.",
        ),
        (
            "A simple repair before replacing a bag",
            "A loose seam or worn strap does not always mean a bag is finished. A small repair can extend its useful life.",
            "Check the material and the load the repair must support. Start with a modest job and use appropriate tools. For a structural repair, an experienced repair shop may be the better option.",
        ),
        (
            "Finding a place for a quiet hobby",
            "A hobby is easier to return to when the tools are ready. A small dedicated space can reduce the effort of beginning.",
            "Choose a project that fits the time you have. Store sharp or messy tools safely. Enjoyment does not need to become a measure of productivity.",
        ),
        (
            "Organising a useful photo collection",
            "A few clear folders and a backup can make family photographs easier to find. A simple system is easier to maintain than a perfect one.",
            "Begin with recent images and remove accidental duplicates carefully. Keep originals when editing. Ask before sharing images of other people.",
        ),
        (
            "A welcoming corner for a houseplant",
            "A plant’s position should match its light and space needs. Observing one plant closely is a practical way to learn.",
            "Check the care guidance for the species and keep unsuitable plants away from pets or children. Change watering with conditions. A fixed weekly schedule may not suit every season.",
        ),
    ],
}
items = []
for cat, rows in CONTENT.items():
    for title, abstract, body in rows:
        items.append(
            {
                "id": f"demo-{len(items) + 1:03}",
                "category": cat,
                "subcategory": cat,
                "title": title,
                "abstract": abstract,
                "body": body,
                "source": "FeedRank demo collection",
            }
        )
Path("catalog/demo.json").write_text(json.dumps(items, indent=2) + "\n")
