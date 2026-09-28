// The product tour on /how-it-works: one screenshot (public/tour/, 1440×900) per stop.

export type TourStop = {
  id: string;
  area: "Shop" | "Staff console";
  title: string;
  image: string;
  text: string[];
};

export const TOUR: TourStop[] = [
  {
    id: "storefront",
    area: "Shop",
    title: "The VoltHaven storefront",
    image: "/tour/home.jpg",
    text: [
      "VoltHaven is a fictional electronics shop built so complaints have a realistic setting: real-looking products, prices, orders, delivery dates and warranties.",
      "Customers browse and buy here; when something goes wrong, the ways to complain are one click away.",
    ],
  },
  {
    id: "catalogue",
    area: "Shop",
    title: "Catalogue",
    image: "/tour/shop.jpg",
    text: [
      "Products by category, with search. Administrators manage the catalogue and its images from the staff console.",
    ],
  },
  {
    id: "product",
    area: "Shop",
    title: "Product page",
    image: "/tour/product.jpg",
    text: [
      "Each product shows its delivery estimate, return window and warranty. These are the promises a complaint is later checked against.",
    ],
  },
  {
    id: "help",
    area: "Shop",
    title: "Help centre",
    image: "/tour/help.jpg",
    text: [
      "Answers to common questions, order tracking and the full delivery, returns and warranty policies.",
      "Signed-in customers can open the support chat: the assistant asks a few questions, links the right order and files the complaint for them.",
    ],
  },
  {
    id: "contact",
    area: "Shop",
    title: "Contact us",
    image: "/tour/contact.jpg",
    text: [
      "The web-form channel. Problems with an order are filed as complaints straight away; other messages go to the enquiries inbox.",
      "Card numbers and passwords typed into the form are hidden before anything is stored or sent to the model.",
    ],
  },
];
