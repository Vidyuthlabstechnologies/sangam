import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { cn } from "../lib/utils";
import { useAuth, useRequireAuth } from "../lib/auth";
import { Button } from "./ui/button";

const navItems = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/workflows", label: "Workflows", icon: "⚡" },
  { href: "/workflows/new", label: "Builder", icon: "🔧" },
  { href: "/approvals", label: "Approvals", icon: "✅" },
  { href: "/actors", label: "Actors", icon: "👥" },
  { href: "/templates", label: "Templates", icon: "📋" },
  { href: "/capabilities", label: "Discovery", icon: "🔍" },
];

export function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, logout } = useAuth();
  const { isLoading } = useRequireAuth();

  if (isLoading) return null;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-white sticky top-0 z-50">
        <div className="flex h-16 items-center px-6 max-w-7xl mx-auto">
          <Link to="/" className="flex items-center gap-2 font-bold text-xl">
            <span className="text-sangam-600">Sangam</span>
          </Link>
          <nav className="ml-10 flex gap-1 overflow-x-auto">
            {navItems.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-colors whitespace-nowrap",
                  location.pathname === item.href
                    ? "bg-sangam-50 text-sangam-700"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                )}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            >
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="p-6 max-w-7xl mx-auto">
        <Outlet />
      </main>
    </div>
  );
}
