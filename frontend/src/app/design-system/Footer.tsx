import { Link } from "react-router";

export function Footer() {
  return (
    <footer className="bg-secondary pt-24 pb-12 px-6 md:px-12 mt-24">
      <div className="max-w-[1400px] mx-auto grid grid-cols-1 md:grid-cols-2 gap-16 md:gap-32 mb-20">
        <div>
          <h2 className="font-serif text-3xl md:text-5xl text-foreground font-light max-w-xl leading-[1.15]">
            Our wedding planners will leave you breathless on your <span className="italic">special day</span>.
          </h2>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-8">
          <div className="flex flex-col gap-4">
            <h5 className="font-sans text-[10px] uppercase tracking-[0.25em] text-foreground/50 mb-2">
              Find us
            </h5>
            <p className="font-sans text-[12px] text-foreground/80 leading-relaxed uppercase">
              Windhover, Enniskerry
              <br />
              Ireland
            </p>
          </div>
          <div className="flex flex-col gap-4">
            <h5 className="font-sans text-[10px] uppercase tracking-[0.25em] text-foreground/50 mb-2">
              Connect
            </h5>
            <a href="#" className="font-sans text-[12px] text-foreground/80 uppercase tracking-wide hover:text-primary transition-colors">
              Instagram
            </a>
            <a href="#" className="font-sans text-[12px] text-foreground/80 uppercase tracking-wide hover:text-primary transition-colors">
              Pinterest
            </a>
            <a href="#" className="font-sans text-[12px] text-foreground/80 uppercase tracking-wide hover:text-primary transition-colors">
              Facebook
            </a>
          </div>
          <div className="flex flex-col gap-4">
            <h5 className="font-sans text-[10px] uppercase tracking-[0.25em] text-foreground/50 mb-2">
              Links
            </h5>
            <Link to="/" className="font-sans text-[12px] text-foreground/80 uppercase tracking-wide hover:text-primary transition-colors">
              Home
            </Link>
            <Link to="/experience" className="font-sans text-[12px] text-foreground/80 uppercase tracking-wide hover:text-primary transition-colors">
              Experience
            </Link>
            <Link to="/#portfolio" className="font-sans text-[12px] text-foreground/80 uppercase tracking-wide hover:text-primary transition-colors">
              Portfolio
            </Link>
            <Link to="/#contact" className="font-sans text-[12px] text-foreground/80 uppercase tracking-wide hover:text-primary transition-colors">
              Contact
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-[1400px] mx-auto pt-8 border-t border-primary/10 flex flex-col md:flex-row justify-between items-center gap-4">
        <p className="font-sans text-[10px] uppercase tracking-[0.25em] text-foreground/50">
          VenueFlow Ireland
        </p>
        <p className="font-sans text-[10px] uppercase tracking-[0.25em] text-foreground/50">
          © {new Date().getFullYear()} All Rights Reserved
        </p>
      </div>
    </footer>
  );
}
