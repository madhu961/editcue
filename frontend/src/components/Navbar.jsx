import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { Button } from "@/components/ui/button";
import { LogOut, Menu, X, HelpCircle, Scissors } from "lucide-react";
import { useState } from "react";

const Navbar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/");
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-white/10" data-testid="navbar">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <Link 
            to="/" 
            className="flex items-center gap-2 text-foreground hover:text-primary transition-colors"
            data-testid="nav-logo"
          >
            <Scissors className="w-6 h-6 text-primary" />
            <span className="font-bold text-lg tracking-tight font-['Space_Grotesk']">
              EDITCUE
            </span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-8">
            <Link 
              to="/help" 
              className="text-muted-foreground hover:text-foreground transition-colors flex items-center gap-2 text-sm"
              data-testid="nav-help-link"
            >
              <HelpCircle className="w-4 h-4" />
              Help
            </Link>
            
            {user ? (
              <div className="flex items-center gap-4">
                <Link to="/tool">
                  <Button 
                    variant="outline" 
                    className="border-primary/30 hover:border-primary hover:bg-primary/10"
                    data-testid="nav-tool-btn"
                  >
                    Open Editor
                  </Button>
                </Link>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-muted-foreground" data-testid="nav-user-name">
                    {user.name || user.email}
                  </span>
                  <Button 
                    variant="ghost" 
                    size="icon"
                    onClick={handleLogout}
                    className="text-muted-foreground hover:text-destructive"
                    data-testid="nav-logout-btn"
                  >
                    <LogOut className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ) : (
              <Link to="/">
                <Button 
                  className="bg-primary text-primary-foreground hover:bg-primary/90 font-bold uppercase tracking-wider rounded-sm"
                  data-testid="nav-get-started-btn"
                >
                  Get Started
                </Button>
              </Link>
            )}
          </div>

          {/* Mobile Menu Toggle */}
          <button 
            className="md:hidden text-foreground"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            data-testid="nav-mobile-toggle"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden pt-4 pb-2 border-t border-white/10 mt-4">
            <div className="flex flex-col gap-4">
              <Link 
                to="/help" 
                className="text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => setMobileMenuOpen(false)}
                data-testid="nav-mobile-help"
              >
                Help & FAQ
              </Link>
              {user ? (
                <>
                  <Link 
                    to="/tool"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <Button className="w-full bg-primary text-primary-foreground" data-testid="nav-mobile-tool">
                      Open Editor
                    </Button>
                  </Link>
                  <Button 
                    variant="outline" 
                    onClick={() => { handleLogout(); setMobileMenuOpen(false); }}
                    data-testid="nav-mobile-logout"
                  >
                    Logout
                  </Button>
                </>
              ) : (
                <Button 
                  className="w-full bg-primary text-primary-foreground"
                  onClick={() => setMobileMenuOpen(false)}
                  data-testid="nav-mobile-get-started"
                >
                  Get Started
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
