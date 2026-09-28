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
    id: "chat",
    area: "Shop",
    title: "Support chat",
    image: "/tour/chat.jpg",
    text: [
      "Signed-in customers describe the problem in their own words. The assistant asks what it needs, files the complaint and gives the reference straight away.",
      "When a reviewer approves the answer, it appears in the same chat, signed by the support team and citing the policy sections it relies on.",
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
  {
    id: "dashboard",
    area: "Staff console",
    title: "Dashboard",
    image: "/tour/dashboard.jpg",
    text: [
      "The organisation-wide view: volume, escalations, SLA risk and breaches, how often the AI and the Python rules disagree, and the manual-review backlog.",
      "Every figure can be filtered by date, category, department, priority, sentiment and channel.",
    ],
  },
  {
    id: "queue",
    area: "Staff console",
    title: "Complaint queue",
    image: "/tour/queue.jpg",
    text: [
      "Every complaint with its AI classification, priority, escalation level, validation verdict and SLA status. The flag marks complaints that need a person.",
      "Filters and search narrow it down; here it shows only the complaints waiting for manual review.",
    ],
  },
  {
    id: "complaint",
    area: "Staff console",
    title: "A complaint, end to end",
    image: "/tour/detail.jpg",
    text: [
      "One page per complaint: the customer's words, deterministic intake checks (here a safety hazard), supporting documents, and why a human must review it.",
      "On the right, the reviewer decides: approve, edit, reject, reclassify, reassign, escalate or re-analyse. Every decision is recorded with the before and after state.",
    ],
  },
  {
    id: "validation",
    area: "Staff console",
    title: "Python validation (Pipeline 2)",
    image: "/tour/detail-checks.jpg",
    text: [
      "The ground truth. Python classifies the complaint on its own, applies the rule matrix and runs 19 checks, each with a severity and evidence. No AI is involved.",
      "The table compares the AI, the rules and, for the dataset, the expected label field by field; the score and verdict decide whether a person must look.",
    ],
  },
  {
    id: "analysis",
    area: "Staff console",
    title: "AI analysis (Pipeline 1)",
    image: "/tour/detail-ai.jpg",
    text: [
      "The model's recommendation as structured data: category, priority, sentiment, departments, escalation and the reason for its urgency, citing the policy passages it used.",
      "It also lists what is missing and the questions to ask the customer. The model, prompt version, tokens and time are recorded with every run.",
    ],
  },
  {
    id: "review",
    area: "Staff console",
    title: "Manual review queue",
    image: "/tour/review.jpg",
    text: [
      "Complaints where the AI and the rules disagree, policy support is missing, the case is sensitive or a policy changed, most urgent first, each with the reasons.",
    ],
  },
  {
    id: "knowledge",
    area: "Staff console",
    title: "Knowledge base",
    image: "/tour/knowledge.jpg",
    text: [
      "The company's approved policies and procedures. Each upload is versioned, split into passages and embedded for search; only the active version is used to resolve complaints.",
    ],
  },
  {
    id: "analytics",
    area: "Staff console",
    title: "Analytics",
    image: "/tour/analytics.jpg",
    text: [
      "Volume, escalations and repeat complaints over time, by category, product, sentiment and department, with emerging trends called out.",
    ],
  },
  {
    id: "reports",
    area: "Staff console",
    title: "Reports",
    image: "/tour/reports.jpg",
    text: [
      "Nine reports, from the Complaint Intelligence Report to SLA status, policy usage and the GenAI vs Python comparison, each exportable as CSV, Excel or PDF.",
    ],
  },
  {
    id: "import",
    area: "Staff console",
    title: "Import complaints",
    image: "/tour/import.jpg",
    text: [
      "Managers upload a CSV or Excel file of complaints, for example from a call centre. Every row is checked and previewed first; nothing is filed until they import.",
    ],
  },
  {
    id: "rules",
    area: "Staff console",
    title: "Rule matrix",
    image: "/tour/rules.jpg",
    text: [
      "The 111 resolution and escalation rules Python applies: conditions, priority, department, escalation level, required and prohibited actions, and the policy each one enforces.",
      "Administrators edit rules here; every change is versioned and audited.",
    ],
  },
];
