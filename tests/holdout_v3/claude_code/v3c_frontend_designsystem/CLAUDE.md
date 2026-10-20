# Design system monorepo

This repository publishes `@acme/core`, `@acme/icons` and `@acme/tokens`. Package manager is pnpm; Node 20. Tests use Vitest and Testing Library; visual tests run in Chromatic.

## General rules

- Prefer composition over configuration. A component with more than eight props needs a design review.
- Never import from another package's `src/`; use the published entry point.
- Every public export has a docs page under `docs/components/` and at least one story.
- Commit messages follow Conventional Commits; every user-visible change has a changeset.

## Per-component conventions

### Button

`Button` lives in `packages/core/src/Button/`. Props are typed with a discriminated union when variants change the allowed children; never accept `any` for event handlers. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Button story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Button.stories.tsx` and the docs page `docs/components/button.mdx` as well. Tests for Button are in `Button.test.tsx` and should not use snapshots.

### IconButton

`IconButton` lives in `packages/core/src/IconButton/`. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the IconButton story for the `error` state depends on the `feedback` token group; if you rename tokens, update `IconButton.stories.tsx` and the docs page `docs/components/iconbutton.mdx` as well. Tests for IconButton are in `IconButton.test.tsx` and should not use snapshots.

### Link

`Link` lives in `packages/core/src/Link/`. All colors come from tokens; a raw hex value in the component source fails the lint rule `ds/no-raw-color`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the Link story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Link.stories.tsx` and the docs page `docs/components/link.mdx` as well. Tests for Link are in `Link.test.tsx` and should not use snapshots.

### TextField

`TextField` lives in `packages/core/src/TextField/`. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the TextField story for the `error` state depends on the `feedback` token group; if you rename tokens, update `TextField.stories.tsx` and the docs page `docs/components/textfield.mdx` as well. Tests for TextField are in `TextField.test.tsx` and should not use snapshots.

### TextArea

`TextArea` lives in `packages/core/src/TextArea/`. Forward refs to the outermost interactive element. Spread remaining props after our own so consumers can override data attributes. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the TextArea story for the `error` state depends on the `feedback` token group; if you rename tokens, update `TextArea.stories.tsx` and the docs page `docs/components/textarea.mdx` as well. Tests for TextArea are in `TextArea.test.tsx` and should not use snapshots.

### Select

`Select` lives in `packages/core/src/Select/`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the Select story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Select.stories.tsx` and the docs page `docs/components/select.mdx` as well. Tests for Select are in `Select.test.tsx` and should not use snapshots.

### Combobox

`Combobox` lives in `packages/core/src/Combobox/`. Props are typed with a discriminated union when variants change the allowed children; never accept `any` for event handlers. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Combobox story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Combobox.stories.tsx` and the docs page `docs/components/combobox.mdx` as well. Tests for Combobox are in `Combobox.test.tsx` and should not use snapshots.

### Checkbox

`Checkbox` lives in `packages/core/src/Checkbox/`. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Checkbox story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Checkbox.stories.tsx` and the docs page `docs/components/checkbox.mdx` as well. Tests for Checkbox are in `Checkbox.test.tsx` and should not use snapshots.

### RadioGroup

`RadioGroup` lives in `packages/core/src/RadioGroup/`. All colors come from tokens; a raw hex value in the component source fails the lint rule `ds/no-raw-color`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the RadioGroup story for the `error` state depends on the `feedback` token group; if you rename tokens, update `RadioGroup.stories.tsx` and the docs page `docs/components/radiogroup.mdx` as well. Tests for RadioGroup are in `RadioGroup.test.tsx` and should not use snapshots.

### Switch

`Switch` lives in `packages/core/src/Switch/`. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Switch story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Switch.stories.tsx` and the docs page `docs/components/switch.mdx` as well. Tests for Switch are in `Switch.test.tsx` and should not use snapshots.

### Slider

`Slider` lives in `packages/core/src/Slider/`. Forward refs to the outermost interactive element. Spread remaining props after our own so consumers can override data attributes. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Slider story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Slider.stories.tsx` and the docs page `docs/components/slider.mdx` as well. Tests for Slider are in `Slider.test.tsx` and should not use snapshots.

### DatePicker

`DatePicker` lives in `packages/core/src/DatePicker/`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the DatePicker story for the `error` state depends on the `feedback` token group; if you rename tokens, update `DatePicker.stories.tsx` and the docs page `docs/components/datepicker.mdx` as well. Tests for DatePicker are in `DatePicker.test.tsx` and should not use snapshots.

### Modal

`Modal` lives in `packages/core/src/Modal/`. Props are typed with a discriminated union when variants change the allowed children; never accept `any` for event handlers. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Modal story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Modal.stories.tsx` and the docs page `docs/components/modal.mdx` as well. Tests for Modal are in `Modal.test.tsx` and should not use snapshots.

### Drawer

`Drawer` lives in `packages/core/src/Drawer/`. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Drawer story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Drawer.stories.tsx` and the docs page `docs/components/drawer.mdx` as well. Tests for Drawer are in `Drawer.test.tsx` and should not use snapshots.

### Popover

`Popover` lives in `packages/core/src/Popover/`. All colors come from tokens; a raw hex value in the component source fails the lint rule `ds/no-raw-color`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the Popover story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Popover.stories.tsx` and the docs page `docs/components/popover.mdx` as well. Tests for Popover are in `Popover.test.tsx` and should not use snapshots.

### Tooltip

`Tooltip` lives in `packages/core/src/Tooltip/`. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Tooltip story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Tooltip.stories.tsx` and the docs page `docs/components/tooltip.mdx` as well. Tests for Tooltip are in `Tooltip.test.tsx` and should not use snapshots.

### Toast

`Toast` lives in `packages/core/src/Toast/`. Forward refs to the outermost interactive element. Spread remaining props after our own so consumers can override data attributes. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Toast story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Toast.stories.tsx` and the docs page `docs/components/toast.mdx` as well. Tests for Toast are in `Toast.test.tsx` and should not use snapshots.

### Banner

`Banner` lives in `packages/core/src/Banner/`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the Banner story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Banner.stories.tsx` and the docs page `docs/components/banner.mdx` as well. Tests for Banner are in `Banner.test.tsx` and should not use snapshots.

### Tabs

`Tabs` lives in `packages/core/src/Tabs/`. Props are typed with a discriminated union when variants change the allowed children; never accept `any` for event handlers. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Tabs story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Tabs.stories.tsx` and the docs page `docs/components/tabs.mdx` as well. Tests for Tabs are in `Tabs.test.tsx` and should not use snapshots.

### Accordion

`Accordion` lives in `packages/core/src/Accordion/`. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Accordion story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Accordion.stories.tsx` and the docs page `docs/components/accordion.mdx` as well. Tests for Accordion are in `Accordion.test.tsx` and should not use snapshots.

### Breadcrumbs

`Breadcrumbs` lives in `packages/core/src/Breadcrumbs/`. All colors come from tokens; a raw hex value in the component source fails the lint rule `ds/no-raw-color`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the Breadcrumbs story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Breadcrumbs.stories.tsx` and the docs page `docs/components/breadcrumbs.mdx` as well. Tests for Breadcrumbs are in `Breadcrumbs.test.tsx` and should not use snapshots.

### Pagination

`Pagination` lives in `packages/core/src/Pagination/`. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Pagination story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Pagination.stories.tsx` and the docs page `docs/components/pagination.mdx` as well. Tests for Pagination are in `Pagination.test.tsx` and should not use snapshots.

### Table

`Table` lives in `packages/core/src/Table/`. Forward refs to the outermost interactive element. Spread remaining props after our own so consumers can override data attributes. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Table story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Table.stories.tsx` and the docs page `docs/components/table.mdx` as well. Tests for Table are in `Table.test.tsx` and should not use snapshots.

### DataGrid

`DataGrid` lives in `packages/core/src/DataGrid/`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the DataGrid story for the `error` state depends on the `feedback` token group; if you rename tokens, update `DataGrid.stories.tsx` and the docs page `docs/components/datagrid.mdx` as well. Tests for DataGrid are in `DataGrid.test.tsx` and should not use snapshots.

### Card

`Card` lives in `packages/core/src/Card/`. Props are typed with a discriminated union when variants change the allowed children; never accept `any` for event handlers. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Card story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Card.stories.tsx` and the docs page `docs/components/card.mdx` as well. Tests for Card are in `Card.test.tsx` and should not use snapshots.

### Avatar

`Avatar` lives in `packages/core/src/Avatar/`. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Avatar story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Avatar.stories.tsx` and the docs page `docs/components/avatar.mdx` as well. Tests for Avatar are in `Avatar.test.tsx` and should not use snapshots.

### Badge

`Badge` lives in `packages/core/src/Badge/`. All colors come from tokens; a raw hex value in the component source fails the lint rule `ds/no-raw-color`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the Badge story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Badge.stories.tsx` and the docs page `docs/components/badge.mdx` as well. Tests for Badge are in `Badge.test.tsx` and should not use snapshots.

### Tag

`Tag` lives in `packages/core/src/Tag/`. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Tag story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Tag.stories.tsx` and the docs page `docs/components/tag.mdx` as well. Tests for Tag are in `Tag.test.tsx` and should not use snapshots.

### Skeleton

`Skeleton` lives in `packages/core/src/Skeleton/`. Forward refs to the outermost interactive element. Spread remaining props after our own so consumers can override data attributes. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Skeleton story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Skeleton.stories.tsx` and the docs page `docs/components/skeleton.mdx` as well. Tests for Skeleton are in `Skeleton.test.tsx` and should not use snapshots.

### Spinner

`Spinner` lives in `packages/core/src/Spinner/`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the Spinner story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Spinner.stories.tsx` and the docs page `docs/components/spinner.mdx` as well. Tests for Spinner are in `Spinner.test.tsx` and should not use snapshots.

### ProgressBar

`ProgressBar` lives in `packages/core/src/ProgressBar/`. Props are typed with a discriminated union when variants change the allowed children; never accept `any` for event handlers. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the ProgressBar story for the `error` state depends on the `feedback` token group; if you rename tokens, update `ProgressBar.stories.tsx` and the docs page `docs/components/progressbar.mdx` as well. Tests for ProgressBar are in `ProgressBar.test.tsx` and should not use snapshots.

### Menu

`Menu` lives in `packages/core/src/Menu/`. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Menu story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Menu.stories.tsx` and the docs page `docs/components/menu.mdx` as well. Tests for Menu are in `Menu.test.tsx` and should not use snapshots.

### NavBar

`NavBar` lives in `packages/core/src/NavBar/`. All colors come from tokens; a raw hex value in the component source fails the lint rule `ds/no-raw-color`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the NavBar story for the `error` state depends on the `feedback` token group; if you rename tokens, update `NavBar.stories.tsx` and the docs page `docs/components/navbar.mdx` as well. Tests for NavBar are in `NavBar.test.tsx` and should not use snapshots.

### SideNav

`SideNav` lives in `packages/core/src/SideNav/`. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the SideNav story for the `error` state depends on the `feedback` token group; if you rename tokens, update `SideNav.stories.tsx` and the docs page `docs/components/sidenav.mdx` as well. Tests for SideNav are in `SideNav.test.tsx` and should not use snapshots.

### Stepper

`Stepper` lives in `packages/core/src/Stepper/`. Forward refs to the outermost interactive element. Spread remaining props after our own so consumers can override data attributes. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Stepper story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Stepper.stories.tsx` and the docs page `docs/components/stepper.mdx` as well. Tests for Stepper are in `Stepper.test.tsx` and should not use snapshots.

### FileUpload

`FileUpload` lives in `packages/core/src/FileUpload/`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the FileUpload story for the `error` state depends on the `feedback` token group; if you rename tokens, update `FileUpload.stories.tsx` and the docs page `docs/components/fileupload.mdx` as well. Tests for FileUpload are in `FileUpload.test.tsx` and should not use snapshots.

### EmptyState

`EmptyState` lives in `packages/core/src/EmptyState/`. Props are typed with a discriminated union when variants change the allowed children; never accept `any` for event handlers. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the EmptyState story for the `error` state depends on the `feedback` token group; if you rename tokens, update `EmptyState.stories.tsx` and the docs page `docs/components/emptystate.mdx` as well. Tests for EmptyState are in `EmptyState.test.tsx` and should not use snapshots.

### Divider

`Divider` lives in `packages/core/src/Divider/`. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode.
Known gotcha: the Divider story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Divider.stories.tsx` and the docs page `docs/components/divider.mdx` as well. Tests for Divider are in `Divider.test.tsx` and should not use snapshots.

### Stack

`Stack` lives in `packages/core/src/Stack/`. All colors come from tokens; a raw hex value in the component source fails the lint rule `ds/no-raw-color`. Animations respect `prefers-reduced-motion`; durations come from the motion tokens, never literals.
Known gotcha: the Stack story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Stack.stories.tsx` and the docs page `docs/components/stack.mdx` as well. Tests for Stack are in `Stack.test.tsx` and should not use snapshots.

### Grid

`Grid` lives in `packages/core/src/Grid/`. Stories must cover default, hover, focus-visible, disabled, and the dark theme. Add a density story when the component has a compact mode. The default size is `md`. Changing the default is a breaking change and needs a changeset marked major.
Known gotcha: the Grid story for the `error` state depends on the `feedback` token group; if you rename tokens, update `Grid.stories.tsx` and the docs page `docs/components/grid.mdx` as well. Tests for Grid are in `Grid.test.tsx` and should not use snapshots.
