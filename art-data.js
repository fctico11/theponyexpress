// The Art Tent: where artists submit work for future drops. Edit this file; you don't need to touch arttent.html.
//
//   next:       the drop you're booking art for, once its theme is set, e.g. { no: "002", title: "Jungle" }.
//               Leave it null and the page books art for future drops in general.
//   deadline:   "YYYY-MM-DD", the last day to submit for that drop. Leave it "" for rolling submissions.
//   brief:      a few sentences on what to make
//   wanted:     the kinds of work you're after, shown as tags
//   uploadUrl:  where the form sends work once uploads are switched on (UploadThing).
//               Leave it "" and the form says uploads open soon instead of sending.
//
// featured: art that has gone out in a drop, newest first. Each one:
//   { name, handle: "@someone", title, drop: "002", image: "media/art/002-someone.jpg", alt }
// Leave the list empty to show "your art here" tiles.

window.ART = {
  next: null,
  deadline: "",
  brief: [
    "Every drop digs into a different sound, scene or era of rave, and every one saves space for art from the floor.",
    "Send us what you make: drawings, paintings, digital art, flyer designs, anything made by your own hand. No AI-generated work, ever. We'll match pieces to upcoming drops as the themes land, and email you when yours is picked.",
  ],
  wanted: [
    "Drawing",
    "Painting",
    "Digital art",
    "Illustration",
    "Flyer design",
    "Mixed media",
  ],
  uploadUrl: "",

  featured: [],
};
