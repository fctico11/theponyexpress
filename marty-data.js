// Everything on Marty's page that changes over time lives here.
// Edit this file; you don't need to touch marty.html.

window.MARTY = {
  // Every rave Marty has been to or is going to, in any order.
  // The page sorts them itself: dates in the future show under
  // "Where he'll be next", dates in the past under "Where he's been".
  //
  //   date:  "YYYY-MM-DD" (first day)
  //   end:   optional last day, for multi-day festivals
  //   event: name of the party or festival
  //   place: venue and/or city
  //   note:  optional one-liner
  stops: [
    {
      date: "2027-05-14",
      end: "2027-05-23",
      event: "EDC Las Vegas",
      place: "Las Vegas Motor Speedway, NV",
      note: "Two weekends this year. Which one he's at is still to be confirmed.",
    },
    {
      date: "2026-10-30",
      end: "2026-10-31",
      event: "Escape Halloween",
      place: "NOS Events Center, San Bernardino, CA",
      note: "",
    },
    {
      date: "2026-08-07",
      end: "2026-08-09",
      event: "Elements Music & Arts Festival",
      place: "Pocono Raceway, Long Pond, PA",
      note: "",
    },
  ],

  // Real photos and videos of Marty. Put the files in media/marty/
  // and list them here. Leave the list empty to show "coming soon" tiles.
  //
  //   type:    "image" or "video"
  //   src:     path to the file, e.g. "media/marty/front-left.jpg"
  //   caption: where and when
  //   alt:     (images) what's in the photo, for people who can't see it
  //   poster:  (videos, optional) a still image to show before it plays
  //
  // The four entries below are AI-generated PLACEHOLDERS, not real photos
  // of Marty. Replace them with the real thing.
  media: [
    { type: "image", src: "media/marty/placeholder-night.webp", caption: "Placeholder image · night set", alt: "A zebra finger puppet held up on one finger above a festival crowd, green and pink lasers behind." },
    { type: "video", src: "media/marty/placeholder-night.mp4", caption: "Placeholder video", poster: "media/marty/placeholder-night.webp" },
    { type: "image", src: "media/marty/placeholder-sunset.webp", caption: "Placeholder image · sunset set", alt: "A zebra finger puppet held up on one finger at a forest festival at sunset." },
    { type: "image", src: "media/marty/placeholder-halloween.webp", caption: "Placeholder image · Halloween", alt: "A zebra finger puppet held up on one finger at an indoor Halloween rave with orange and purple lights." },
  ],
};
