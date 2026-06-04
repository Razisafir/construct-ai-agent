import useAppStore from "../stores/useAppStore";

interface ActivityIcon {
  id: string;
  icon: string;
  label: string;
}

const ACTIVITY_ICONS: ActivityIcon[] = [
  { id: "explorer", icon: "folder", label: "Explorer" },
  { id: "search", icon: "search", label: "Search" },
  { id: "git", icon: "account_tree", label: "Source Control" },
  { id: "debug", icon: "bug_report", label: "Run and Debug" },
  { id: "extensions", icon: "extension", label: "Extensions" },
  { id: "mcp", icon: "hub", label: "MCP" },
];

function ActivityBar() {
  const activeSidebarTab = useAppStore((s) => s.activeSidebarTab);
  const setActiveSidebarTab = useAppStore((s) => s.setActiveSidebarTab);
  

  return (
    <nav className="w-12 flex-shrink-0 bg-panel-bg border-r border-border-subtle flex flex-col items-center py-4 gap-2 z-40">
      {ACTIVITY_ICONS.map((item) => {
        const isActive = activeSidebarTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => setActiveSidebarTab(item.id)}
            className={`
              w-10 h-10 flex items-center justify-center rounded-md transition-colors duration-[50ms] relative
              ${isActive
                ? "bg-accent-cyan-dim text-accent-cyan border border-accent-cyan/30"
                : "text-text-secondary hover:text-text-primary bg-transparent border border-transparent"
              }
            `}
            title={item.label}
          >
            <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
            {/* Active indicator bar on left edge */}
            {isActive && (
              <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-6 bg-accent-cyan rounded-r" />
            )}
          </button>
        );
      })}

      {/* Bottom icons: Settings */}
      <div className="mt-auto flex flex-col gap-2">
        <button
          className="w-10 h-10 flex items-center justify-center rounded-md text-text-secondary hover:text-text-primary transition-colors bg-transparent border border-transparent"
          title="Settings"
          onClick={() => {
            window.dispatchEvent(new CustomEvent("construct:open-settings"));
          }}
        >
          <span className="material-symbols-outlined text-[20px]">settings</span>
        </button>
      </div>
    </nav>
  );
}

export default ActivityBar;
