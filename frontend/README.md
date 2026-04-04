# Frontend Structure

This folder contains the frontend components for the Multi-Agent System.

## Folder Structure

```
frontend/
├── css/
│   └── styles.css          # Main stylesheet with all UI styles
├── js/
│   └── app.js              # Main JavaScript application logic
├── components/
│   ├── agent-chip.html     # Reusable agent chip component
│   └── history-item.html   # Reusable history item component
├── assets/                 # Static assets (images, icons, etc.)
└── index.html              # Main HTML file
```

## Key Features

### 🎨 Modern UI/UX Design
- **Dark theme** with gradient backgrounds and glassmorphism effects
- **Responsive design** that works on all screen sizes
- **Smooth animations** and transitions for better user experience
- **Professional color scheme** suitable for business applications

### 📱 Component-Based Architecture
- **Modular CSS** organized into logical sections
- **Separate JavaScript** for better maintainability
- **Reusable components** for consistent UI elements
- **Clean HTML structure** with semantic markup

### ⚡ Performance Optimizations
- **Efficient polling** with 300ms intervals for real-time updates
- **Smart caching** to prevent duplicate log entries
- **Optimized rendering** with proper DOM manipulation
- **Minimal network requests** with intelligent refresh logic

### 🔧 Technical Features
- **Real-time logging** with live agent activity display
- **Interactive agent chips** that activate during execution
- **Professional report rendering** with formatted output
- **Error handling** and user feedback systems
- **Analytics dashboard** with live metrics

## File Descriptions

### `css/styles.css`
- Complete styling system with CSS custom properties
- Responsive design with mobile-first approach
- Professional animations and transitions
- Component-specific styles for all UI elements

### `js/app.js`
- Main application logic and API communication
- Real-time polling and status management
- UI state management and updates
- Error handling and user feedback
- Analytics and history management

### `index.html`
- Clean, semantic HTML structure
- Proper resource loading (CSS first, then JS)
- Accessibility considerations
- SEO-friendly markup

### `components/`
- Reusable HTML components for consistency
- Template-based structure for easy maintenance
- Modular design for future enhancements

## Usage

The frontend is automatically served by the FastAPI backend at:
- Main interface: `http://localhost:8000/index.html`
- Static assets: `http://localhost:8000/static/frontend/`

## Development

When making changes:
1. Update CSS in `css/styles.css` for styling changes
2. Update JavaScript in `js/app.js` for functionality changes
3. Update HTML in `index.html` for structure changes
4. Add new components to the `components/` folder for reusability

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- CSS Grid and Flexbox support required
- ES6+ JavaScript features used
