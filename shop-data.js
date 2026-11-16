// The shop's products. Edit this file; you don't need to touch shop.html.
//
//   name:   product name
//   blurb:  one or two short sentences
//   price:  number, in dollars
//   buyUrl: where the Buy button goes, e.g. a Stripe Payment Link.
//           Leave it "" and the button shows "Coming soon" instead.
//   image:  optional path to a real photo, e.g. "media/shop/single.jpg".
//           Without one, the page draws the bracelet from the fields below.
//   beads:  bead colours, repeated around the bracelet
//   word:   optional letter beads, e.g. "PLUR"
//   rows:   optional number of rows (1 = single, 3+ = cuff)
//
//
// Perlers (the `perlers` list further down) use the same name, blurb, price,
// buyUrl and image fields, plus:
//   pixels:  the design, one string per row, one character per bead.
//            "." is an empty peg. Rows should all be the same length.
//   colours: which colour each character stands for
//
// Everything below is a PLACEHOLDER: names, blurbs, prices and designs.

window.SHOP = {
  currency: "USD",
  products: [
    {
      name: "The Single",
      blurb: "One strand in house colours. The classic trade.",
      price: 4,
      buyUrl: "",
      beads: ["#c6ff1f", "#ff2a93", "#050506", "#f4f2ec"],
    },
    {
      name: "PLUR Single",
      blurb: "Letter beads up top, stripes all the way round.",
      price: 5,
      buyUrl: "",
      beads: ["#050506", "#f4f2ec"],
      word: "PLUR",
    },
    {
      name: "Marty Single",
      blurb: "His name, his stripes, a little pink for the cap.",
      price: 5,
      buyUrl: "",
      beads: ["#f4f2ec", "#050506", "#ff2a93"],
      word: "MARTY",
    },
    {
      name: "Stripe Stack",
      blurb: "Five singles, one in each house colour. Keep two, trade three.",
      price: 15,
      buyUrl: "",
      beads: ["#19e6ff", "#7a3bff", "#ff2a93", "#c6ff1f"],
      rows: 2,
    },
    {
      name: "The Cuff",
      blurb: "Three rows, wide and loud. Takes a while to make.",
      price: 28,
      buyUrl: "",
      beads: ["#ff2a93", "#c6ff1f", "#7a3bff", "#050506", "#19e6ff"],
      rows: 3,
    },
    {
      name: "Mystery Handful",
      blurb: "Three singles, picked by Marty. No peeking, no swaps.",
      price: 10,
      buyUrl: "",
      beads: ["#7a3bff", "#19e6ff", "#f4f2ec", "#ff2a93", "#c6ff1f", "#050506"],
    },
  ],

  perlers: [
    {
      name: "Marty Perler",
      blurb: "The carrier himself, in fused beads. Hang him off a single.",
      price: 8,
      buyUrl: "",
      colours: { k: "#050506", w: "#f4f2ec", p: "#ff2a93" },
      pixels: [
        ".kk......kk.",
        ".kwk....kwk.",
        "..kkwwwwkk..",
        "..wwkkkkww..",
        ".wwwwwwwwww.",
        ".kkwkwwkwkk.",
        ".wwwwwwwwww.",
        ".kkwwwwwwkk.",
        "..wwwwwwww..",
        "..kkkkkkkk..",
        "..kpkkkkpk..",
        "...kkkkkk...",
      ],
    },
    {
      name: "Acid Smiley",
      blurb: "The oldest face in the building, in house green.",
      price: 6,
      buyUrl: "",
      colours: { a: "#c6ff1f", k: "#050506" },
      pixels: [
        "....aaaa....",
        "..aaaaaaaa..",
        ".aaaaaaaaaa.",
        ".aakaaaakaa.",
        "aaakaaaakaaa",
        "aaakaaaakaaa",
        "aaaaaaaaaaaa",
        "aakaaaaaakaa",
        ".aakaaaakaa.",
        ".aaakkkkaaa.",
        "..aaaaaaaa..",
        "....aaaa....",
      ],
    },
    {
      name: "PLUR Heart",
      blurb: "Pink, loud, and built to be handed over.",
      price: 6,
      buyUrl: "",
      colours: { p: "#ff2a93", w: "#f4f2ec" },
      pixels: [
        "............",
        ".ppp....ppp.",
        "ppwpp..ppppp",
        "pwpppppppppp",
        "pppppppppppp",
        "pppppppppppp",
        ".pppppppppp.",
        "..pppppppp..",
        "...pppppp...",
        "....pppp....",
        ".....pp.....",
        "............",
      ],
    },
    {
      name: "Night Shroom",
      blurb: "UV cap, acid spots. Glows under blacklight in spirit.",
      price: 7,
      buyUrl: "",
      colours: { u: "#7a3bff", a: "#c6ff1f", w: "#f4f2ec" },
      pixels: [
        "....uuuu....",
        "..uuuuauuu..",
        ".uaauuuuuuu.",
        ".uaauuuaauu.",
        "uuuuuuuaauuu",
        "uuuuuuuuuuuu",
        ".uuuuuuuuuu.",
        "....wwww....",
        "....wwww....",
        "....wwww....",
        "...wwwwww...",
        "............",
      ],
    },
    {
      name: "Little Green Guy",
      blurb: "Came for the bass, stayed for the people.",
      price: 7,
      buyUrl: "",
      colours: { a: "#c6ff1f", k: "#050506" },
      pixels: [
        "...aaaaaa...",
        "..aaaaaaaa..",
        ".aaaaaaaaaa.",
        ".aaaaaaaaaa.",
        ".akkkaakkka.",
        ".akkkaakkka.",
        "..akkaakka..",
        "..aaaaaaaa..",
        "...aaaaaa...",
        "....akka....",
        "....aaaa....",
        ".....aa.....",
      ],
    },
    {
      name: "Your Design",
      blurb: "Send an idea, get it back in beads. Simple shapes work best.",
      price: 12,
      buyUrl: "",
      colours: { c: "#19e6ff" },
      pixels: [
        "...cccccc...",
        "..cccccccc..",
        ".ccc....ccc.",
        ".ccc....ccc.",
        "........ccc.",
        "......cccc..",
        ".....ccc....",
        "....ccc.....",
        "....ccc.....",
        "............",
        "....ccc.....",
        "....ccc.....",
      ],
    },
  ],
};
