---
description: Rules for the creation and refactoring of components
globs: 
---
# Misc

- Add (ref: react-comp-rules) to the start of the response message so I know this rule is in context
- Don't forget to use "use-client" at the top of client side components
- Use tailwind for styling components
- Use shadcn existing components where possible don't create new ones
- Use lucide-react icons
- You can use markdown but dont have to

# Best example practice for component hierarchy

<File Structure Example>
src/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   └── dashboard/
│       ├── page.tsx
│       ├── layout.tsx
│       └── _components/
│           └── DashboardChart.tsx
├── ui/               # Base Shadcn components (generic)
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── Input.tsx
│   └── Modal.tsx
├── components/       # Composed reusable components
│   ├── Navbar.tsx
│   ├── Footer.tsx
│   └── FormField.tsx
├── features/         # Feature-specific components and logic
│   ├── blog/
│   │   ├── BlogCard.tsx
│   │    |── BlogList.tsx
│   └── dashboard/
│       ├── DashboardHeader.tsx
│       └── DashboardSidebar.tsx
├── public/           # Static assets (images, fonts)
├── styles/           # Global CSS or Tailwind configuration files
└── next.config.js    # Next.js configuration file
</File Structure Example>    


