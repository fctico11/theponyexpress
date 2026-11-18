// The drops: what's coming next, and what's already gone out.
// Edit this file; you don't need to touch drops.html.
//
// current: the drop being teased right now.
//   no:       the drop number, e.g. "001"
//   title:    the sound, scene or era it's about
//   ships:    "YYYY-MM-DD", the 1st it goes out. Leave it "" until you've picked
//             the date: the page says "date coming soon" and hides the countdown.
//   kicker:   one short line under the title
//   blurb:    a few sentences on what it's about. Tease the theme, not the contents.
//   chapters: the zine's chapter titles, as a teaser tracklist
//   extras:   one line about the stickers, trinkets and art, without spoilers
//
// past: drops that have gone out, newest first. Each one:
//   { no, title, shipped: "YYYY-MM-DD", blurb, image: "media/drops/001.jpg" (optional) }

window.DROPS = {
  current: {
    no: "001",
    title: "Origins of Rave",
    ships: "",
    kicker: "Where it all started, and how it got to be what it is today.",
    blurb: [
      "Before the festivals, the wristbands and the main stages, there were basements, warehouses and fields, and a few records that changed everything.",
      "Drop 001 goes back to the start: where rave came from, the people and places that built it, and how it travelled from those first rooms to the dancefloor you were on last weekend.",
    ],
    chapters: [
      "Before the rave",
      "The warehouse",
      "Acid",
      "Summers of love",
      "Fields and motorways",
      "Smiley faces and PLUR",
      "You are here",
    ],
    extras: "Art, stickers and trinkets in old-school neon, made for the era. That's all we're saying.",
  },

  past: [],
};
