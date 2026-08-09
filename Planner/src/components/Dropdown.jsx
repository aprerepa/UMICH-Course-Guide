import { ChevronDownIcon } from "./Icons";

const styles = {
  wrapper: {
    position: "relative",
    display: "inline-block",
    width: "100%",
  },
  trigger: (isOpen) => ({
    width: "100%",
    padding: "10px 14px",
    borderRadius: "8px",
    border: isOpen ? "2px solid #4a7cf6" : "1.5px solid #d4d4d4",
    backgroundColor: "#fff",
    fontSize: "14.5px",
    color: "#222",
    cursor: "pointer",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    boxSizing: "border-box",
    outline: "none",
    userSelect: "none",
  }),
  triggerPlaceholder: {
    color: "#aaa",
  },
  menu: {
    position: "absolute",
    top: "calc(100% + 4px)",
    left: 0,
    right: 0,
    backgroundColor: "#2d2d2d",
    border: "1px solid #444",
    borderRadius: "8px",
    zIndex: 100,
    maxHeight: "240px",
    overflowY: "auto",
    boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
  },
  menuItemBase: {
    padding: "10px 16px",
    fontSize: "14px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
};

/**
 * @param {string}   value          - Currently selected value (empty string = none)
 * @param {Function} onChange        - Called with the new value when an option is selected
 * @param {Array}    options         - Array of { label, value } objects
 * @param {string}   placeholder     - Shown when value is empty
 * @param {boolean}  isOpen          - Whether the dropdown menu is visible
 * @param {Function} onToggle        - Called when the trigger is clicked
 */
export function Dropdown({ value, onChange, options, placeholder, isOpen, onToggle }) {
  const selectedLabel = options.find((o) => o.value === value)?.label ?? "";

  return (
    <div style={styles.wrapper}>
      <div style={styles.trigger(isOpen)} onClick={onToggle}>
        <span style={!value ? styles.triggerPlaceholder : {}}>
          {selectedLabel || placeholder}
        </span>
        <ChevronDownIcon size={14} />
      </div>

      {isOpen && (
        <div style={styles.menu}>
          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <div
                key={opt.value}
                style={{
                  ...styles.menuItemBase,
                  paddingLeft: isSelected ? "16px" : "28px",
                  color: isSelected ? "#fff" : "#e0e0e0",
                  backgroundColor: isSelected ? "#4a7cf6" : "transparent",
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = "#3a3a3a";
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = "transparent";
                }}
                onClick={() => onChange(opt.value)}
              >
                {isSelected && <span style={{ fontSize: "11px" }}>✓</span>}
                {opt.label}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
