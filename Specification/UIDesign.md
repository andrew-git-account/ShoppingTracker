# UI Design - Shopping Tracker

## Visual Structure

### Layout Overview
Two-page design with navigation:
- **Upload Page** (default/home) - Upload receipt photos
- **History Page** - View all receipts with expandable details

### Navigation
Simple tab-style navigation at the top:
```
┌────────────────────────────────────────────┐
│       Shopping Tracker 🛒                  │
│   [Upload]   [History]                     │
├────────────────────────────────────────────┤
│                                            │
│          Page Content Here                 │
│                                            │
└────────────────────────────────────────────┘
```

---

## Page 1: Upload Receipt

### Layout
```
┌─────────────────────────────────────────────┐
│  🛒 Shopping Tracker                        │
│  [Upload*]  [History]                       │
├─────────────────────────────────────────────┤
│                                             │
│    Upload Receipt                           │
│    ─────────────                            │
│                                             │
│    Take or select a photo of your receipt   │
│                                             │
│    ┌──────────────────────────────┐        │
│    │  [Choose File]  No file chosen│        │
│    └──────────────────────────────┘        │
│                                             │
│              [Upload Receipt]               │
│                                             │
│    Supported formats: JPG, JPEG, PNG        │
│    Maximum file size: 5MB                   │
│                                             │
└─────────────────────────────────────────────┘
```

### Features
- Clean, centered form
- File input with clear label
- Large, obvious upload button
- Helper text about supported formats
- After upload: Shows loading spinner → Success/Error message

---

## Page 2: History

### Layout (Collapsed State)
```
┌──────────────────────────────────────────────┐
│  🛒 Shopping Tracker                         │
│  [Upload]  [History*]                        │
├──────────────────────────────────────────────┤
│                                              │
│    Receipt History                           │
│    ──────────────                            │
│    Total Receipts: 5                         │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ ▸ Walmart - May 7, 2026       $45.67   │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ ▸ Target - May 5, 2026        $78.32   │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ ▸ Costco - May 3, 2026       $123.45   │ │
│  └────────────────────────────────────────┘ │
│                                              │
└──────────────────────────────────────────────┘
```

### Layout (One Receipt Expanded)
```
┌──────────────────────────────────────────────┐
│  🛒 Shopping Tracker                         │
│  [Upload]  [History*]                        │
├──────────────────────────────────────────────┤
│                                              │
│    Receipt History                           │
│    ──────────────                            │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ ▾ Walmart - May 7, 2026       $45.67   │ │
│  │                                         │ │
│  │   Items:                                │ │
│  │   • Milk.........................$3.99  │ │
│  │   • Bread........................$2.49  │ │
│  │   • Eggs (x2)...................$6.98  │ │
│  │   • Apples (5 lbs).............$4.95  │ │
│  │   • Chicken Breast.............$15.99  │ │
│  │                                         │ │
│  │   Subtotal:.....................$34.40  │ │
│  │   Tax:..........................$3.27  │ │
│  │   Discount:.....................$0.00  │ │
│  │   ─────────────────────────────────    │ │
│  │   Total:........................$37.67  │ │
│  │                                         │ │
│  │   Saved on: May 7, 2026 at 3:42 PM    │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │ ▸ Target - May 5, 2026        $78.32   │ │
│  └────────────────────────────────────────┘ │
│                                              │
└──────────────────────────────────────────────┘
```

### Features
- Each receipt is a collapsible card
- **Collapsed**: Shows store, date, total (one line)
- **Expanded**: Shows full item list with prices
- Click anywhere on header to expand/collapse
- Uses HTML `<details>` and `<summary>` (no JavaScript needed!)
- Items displayed with quantity if > 1
- Subtotal, tax, discount, total clearly shown
- Most recent receipts at the top

---

## Color Scheme

### Primary Colors
- **Background**: `#f5f5f5` (light gray)
- **Card Background**: `#ffffff` (white)
- **Primary Color**: `#4CAF50` (green - for buttons, active tab)
- **Text**: `#333333` (dark gray)
- **Border**: `#dddddd` (light gray)

### Accent Colors
- **Success**: `#4CAF50` (green)
- **Error**: `#f44336` (red)
- **Info**: `#2196F3` (blue)

### Typography
- **Font**: System fonts (Arial, Helvetica, sans-serif)
- **Headings**: Bold, larger size
- **Body**: Regular weight

---

## Responsive Design

### Desktop (> 768px)
- Max content width: 800px
- Centered on page
- Receipt cards have hover effect

### Mobile (< 768px)
- Full width with padding
- Smaller font sizes
- Touch-friendly buttons (larger)
- Stack elements vertically

---

## User Flow

### Upload Flow
1. User lands on Upload page (default)
2. Clicks "Choose File" → File picker opens
3. Selects receipt image → Filename shown
4. Clicks "Upload Receipt" → Button disabled, shows "Processing..."
5. Success → Shows success message + "View History" link
6. Error → Shows error message + "Try Again" button

### History Flow
1. User clicks "History" tab
2. Sees list of all receipts (collapsed by default)
3. Clicks on a receipt → Expands to show items
4. Clicks again → Collapses
5. Can expand multiple receipts at once

---

## Technical Implementation

### HTML Structure
```html
<!-- Base Template -->
<nav>
  <h1>Shopping Tracker</h1>
  <ul>
    <li><a href="/">Upload</a></li>
    <li><a href="/history">History</a></li>
  </ul>
</nav>
<main>
  <!-- Page content here -->
</main>

<!-- History Page - Expandable Receipt -->
<details class="receipt-card">
  <summary>
    <strong>Store Name</strong>
    <span class="date">Date</span>
    <span class="total">$00.00</span>
  </summary>
  <div class="receipt-details">
    <!-- Items list here -->
  </div>
</details>
```

### CSS Features
- Flexbox for layout
- Clean spacing and padding
- Subtle shadows for depth
- Smooth transitions
- Focus states for accessibility

---

## Future Enhancements (V1.5+)

### With JavaScript
- AJAX upload (no page reload)
- Real-time progress bar
- Filter/search receipts
- Sorting options (date, store, amount)
- Collapse/expand all button

### V2
- Charts and statistics
- Receipt image preview
- Edit functionality
- Delete with confirmation
- Export to CSV

---

## Accessibility

- Semantic HTML (nav, main, section, details)
- Proper heading hierarchy (h1 → h2 → h3)
- Alt text for images (when we add them)
- Focus indicators for keyboard navigation
- Good color contrast (WCAG AA compliant)
- Clear error messages

---

## Mobile Considerations

### Touch Targets
- Buttons: Minimum 44x44px
- Links: Adequate padding
- File input: Large enough to tap

### Performance
- Optimize images before upload
- Keep CSS/HTML lightweight
- Fast page loads

---

This design prioritizes:
✅ **Simplicity** - Easy to understand and use
✅ **Clarity** - Clear information hierarchy
✅ **Functionality** - Core features work well
✅ **No JavaScript** - Works everywhere, degrades gracefully
✅ **Expandability** - Easy to add features later
