// The people behind SupportNova, shown on /team and at the end of blog posts.
// Photos live in public/team/ (square, about 640px).

export type TeamMember = {
  name: string;
  role: "Mentor" | "Student";
  studentId?: string;
  photo: string;
};

export const COMPETITION = {
  name: "TechWiz 7.0",
  tagline: "The World Tech Championship",
  logo: "/team/techwiz-logo.png",
};

export const MENTOR: TeamMember = {
  name: "Gulraeez Gulshan",
  role: "Mentor",
  photo: "/team/gulraeez-gulshan.jpg",
};

export const STUDENTS: TeamMember[] = [
  {
    name: "Samar Minallah",
    role: "Student",
    studentId: "Student1668981",
    photo: "/team/samar-minallah.jpg",
  },
  {
    name: "Alaina Ahmed",
    role: "Student",
    studentId: "Student1696382",
    photo: "/team/alaina-ahmed.jpg",
  },
  { name: "Horiya", role: "Student", studentId: "Student1694879", photo: "/team/horiya.jpg" },
  {
    name: "Rabia Nadeem",
    role: "Student",
    studentId: "Student1575945",
    photo: "/team/rabia-nadeem.jpg",
  },
  {
    name: "Mehwish Irfan",
    role: "Student",
    studentId: "Student1612536",
    photo: "/team/mehwish-irfan.jpg",
  },
];

export const TEAM: TeamMember[] = [MENTOR, ...STUDENTS];
