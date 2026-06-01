---
name: frontend-ui-engineering
version: 1.0.0
category: design
description: Build React components with TypeScript and Tailwind CSS following modern best practices
author: Construct AI
tools_needed: [write_file, read_file, shell, edit_file]
confidence: 0.95
---

# Frontend UI Engineering

## Description

Build production-grade React components using TypeScript for type safety and Tailwind CSS for styling. Follow component-driven development with proper state management, accessibility, and performance considerations.

## When to Use

- Building new UI components or features
- Refactoring class components to functional components with hooks
- Implementing design system components
- Creating responsive, accessible user interfaces
- Building dashboard or data visualization UIs

## Steps

### Step 1: Analyze the Design Requirements

**Tool:** `read_file`
**Parameters:**

```json
{"file_path": "/designs/component-spec.md"}
```

**Validation:** Understand: visual design, interaction states, accessibility requirements, responsive behavior, data requirements.

### Step 2: Define Component Interface

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/components/Button/Button.types.ts",
  "content": "import { ButtonHTMLAttributes } from 'react';\n\nexport type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';\nexport type ButtonSize = 'sm' | 'md' | 'lg';\n\nexport interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {\n  variant?: ButtonVariant;\n  size?: ButtonSize;\n  isLoading?: boolean;\n  isDisabled?: boolean;\n  leftIcon?: React.ReactNode;\n  rightIcon?: React.ReactNode;\n}\n"
}
```

**Validation:** TypeScript types compile without errors. Props extend appropriate HTML attributes.

### Step 3: Implement Component with Tailwind

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/components/Button/Button.tsx",
  "content": "import React from 'react';\nimport { ButtonProps } from './Button.types';\nimport { cn } from '@/lib/utils';\n\nconst variantStyles: Record<ButtonVariant, string> = {\n  primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',\n  secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300 focus:ring-gray-500',\n  danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',\n  ghost: 'bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-gray-500',\n};\n\nconst sizeStyles: Record<ButtonSize, string> = {\n  sm: 'px-3 py-1.5 text-sm',\n  md: 'px-4 py-2 text-base',\n  lg: 'px-6 py-3 text-lg',\n};\n\nexport const Button: React.FC<ButtonProps> = ({\n  variant = 'primary',\n  size = 'md',\n  isLoading = false,\n  isDisabled = false,\n  leftIcon,\n  rightIcon,\n  children,\n  className,\n  ...props\n}) => {\n  return (\n    <button\n      className={cn(\n        'inline-flex items-center justify-center rounded-md font-medium',\n        'focus:outline-none focus:ring-2 focus:ring-offset-2',\n        'transition-colors duration-200',\n        'disabled:opacity-50 disabled:cursor-not-allowed',\n        variantStyles[variant],\n        sizeStyles[size],\n        className\n      )}\n      disabled={isDisabled || isLoading}\n      {...props}\n    >\n      {isLoading && <LoadingSpinner className=\"mr-2\" size=\"sm\" />}\n      {!isLoading && leftIcon && <span className=\"mr-2\">{leftIcon}</span>}\n      {children}\n      {!isLoading && rightIcon && <span className=\"ml-2\">{rightIcon}</span>}\n    </button>\n  );\n};\n"
}
```

**Validation:** Component renders without errors. All variants and sizes display correctly.

### Step 4: Write Component Tests

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/components/Button/Button.test.tsx",
  "content": "import { render, screen, fireEvent } from '@testing-library/react';\nimport { Button } from './Button';\n\ndescribe('Button', () => {\n  it('renders with default variant', () => {\n    render(<Button>Click me</Button>);\n    expect(screen.getByRole('button')).toHaveTextContent('Click me');\n  });\n\n  it('applies variant styles correctly', () => {\n    const { rerender } = render(<Button variant=\"primary\">Btn</Button>);\n    expect(screen.getByRole('button')).toHaveClass('bg-blue-600');\n    \n    rerender(<Button variant=\"danger\">Btn</Button>);\n    expect(screen.getByRole('button')).toHaveClass('bg-red-600');\n  });\n\n  it('is disabled when isDisabled is true', () => {\n    render(<Button isDisabled>Disabled</Button>);\n    expect(screen.getByRole('button')).toBeDisabled();\n  });\n\n  it('shows loading spinner', () => {\n    render(<Button isLoading>Loading</Button>);\n    expect(screen.getByRole('button')).toHaveAttribute('disabled');\n    expect(document.querySelector('svg')).toBeInTheDocument();\n  });\n\n  it('calls onClick handler', () => {\n    const handleClick = jest.fn();\n    render(<Button onClick={handleClick}>Click</Button>);\n    fireEvent.click(screen.getByRole('button'));\n    expect(handleClick).toHaveBeenCalledTimes(1);\n  });\n\n  it('is accessible via keyboard', () => {\n    render(<Button>Focus me</Button>);\n    const button = screen.getByRole('button');\n    button.focus();\n    expect(button).toHaveFocus();\n  });\n});\n"
}
```

**Validation:** All tests pass. Coverage is ≥ 90% for component logic.

### Step 5: Add Storybook Documentation

**Tool:** `write_file`
**Parameters:**

```json
{
  "file_path": "/src/components/Button/Button.stories.tsx",
  "content": "import type { Meta, StoryObj } from '@storybook/react';\nimport { Button } from './Button';\n\nconst meta: Meta<typeof Button> = {\n  title: 'Components/Button',\n  component: Button,\n  tags: ['autodocs'],\n  argTypes: {\n    variant: { control: 'select', options: ['primary', 'secondary', 'danger', 'ghost'] },\n    size: { control: 'select', options: ['sm', 'md', 'lg'] },\n  },\n};\n\nexport default meta;\ntype Story = StoryObj<typeof Button>;\n\nexport const Primary: Story = { args: { children: 'Primary Button', variant: 'primary' } };\nexport const Secondary: Story = { args: { children: 'Secondary', variant: 'secondary' } };\nexport const Danger: Story = { args: { children: 'Delete', variant: 'danger' } };\nexport const Loading: Story = { args: { children: 'Saving...', isLoading: true } };\nexport const Disabled: Story = { args: { children: 'Disabled', isDisabled: true } };\n"
}
```

**Validation:** Storybook starts and all stories render correctly.

### Step 6: Run Quality Checks

**Tool:** `shell`
**Parameters:**

```json
{"command": "npm run lint -- --fix && npm run type-check && npm test -- --coverage --watchAll=false", "description": "Run lint, type-check, and tests"}
```

**Validation:** ESLint passes, TypeScript compiles, all tests pass with ≥ 90% coverage.

## Examples

### Example 1: Data Table Component

**Input:** "Build a sortable, paginated data table."

**Process:**

1. Requirements: Sortable columns, pagination, row selection, responsive
2. Types: TableProps<T>, ColumnDef<T>, SortConfig
3. Implementation: Table, TableHeader, TableBody, TableRow sub-components with Tailwind
4. Tests: Sorting, pagination, selection, accessibility
5. Storybook: Default, sorted, paginated, loading states
6. Quality: All checks pass

**Output:** Reusable, accessible data table with full test coverage.

### Example 2: Modal Dialog

**Input:** "Create an accessible modal dialog component."

**Process:**

1. Requirements: Focus trap, ESC to close, ARIA attributes, backdrop click
2. Types: ModalProps with title, children, onClose, isOpen
3. Implementation: useFocusTrap hook, role="dialog", aria-modal="true"
4. Tests: Focus management, keyboard navigation, close behaviors
5. Storybook: Default, with form, confirmation, large content
6. Quality: a11y audit passes

**Output:** WCAG-compliant modal with proper focus management.

### Example 3: Form with Validation

**Input:** "Build a user registration form with validation."

**Process:**

1. Requirements: Client validation, server validation display, accessible errors
2. Types: FormData, FieldErrors, ValidationRules
3. Implementation: useForm hook, Input components with error states
4. Tests: Valid submission, invalid fields, server errors, accessibility
5. Storybook: Empty form, filled form, error state, loading state
6. Quality: All checks pass

**Output:** Accessible form with comprehensive validation.

## Best Practices

- **Type everything.** Use TypeScript for all props, state, and API responses.
- **Use `cn()` for classes.** Combine Tailwind classes cleanly with conditional logic.
- **Accessibility first.** Include proper ARIA attributes, keyboard navigation, and focus management.
- **Composition over configuration.** Prefer compound components for complex UIs.
- **Custom hooks.** Extract reusable logic into custom hooks (useForm, useFetch, etc.).
- **Lazy load.** Use React.lazy() and dynamic imports for large components.
- **Test interactions.** Use Testing Library to test user interactions, not implementation details.
- **Design tokens.** Use Tailwind config for consistent colors, spacing, and typography.