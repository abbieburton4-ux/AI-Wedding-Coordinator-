import { ArrowRight } from "lucide-react";
import {
  ButtonLink,
  GoldSpecks,
  ReadMoreLink,
  SectionHeading,
} from "../design-system/primitives";
import { IMG } from "../design-system/assets";

export function Landing() {
  return (
    <>
      {/* Hero */}
      <section
        id="home"
        className="relative pt-32 pb-24 md:pt-40 md:pb-32 px-6 md:px-12 max-w-[1600px] mx-auto min-h-[90vh] flex flex-col md:flex-row items-center gap-12 lg:gap-24"
      >
        <div className="flex-1 relative z-10 w-full">
          <GoldSpecks className="top-10 -left-10 hidden md:block" />
          <SectionHeading
            subtitle="Life is an event"
            title="Creating the"
            italic="best day ever"
            className="mb-8"
          />
          <p className="text-muted-foreground font-light leading-relaxed max-w-md mb-10 text-[15px]">
            From intimate ceremonies to grand celebrations, we curate every moment with
            elegance and intention — turning the day you imagine into a memory you'll
            carry forever.
          </p>
          <ButtonLink to="/experience" variant="outline">
            Explore
          </ButtonLink>
        </div>

        <div className="flex-1 w-full relative aspect-[4/5] sm:aspect-[3/4] md:aspect-auto md:h-[80vh] md:max-h-[800px]">
          <GoldSpecks className="bottom-20 -right-8 hidden md:block" />
          <div className="absolute inset-0 right-0 md:-right-12 lg:-right-24 rounded-bl-[120px] overflow-hidden">
            <img
              src={IMG.heroCouple}
              alt="Couple on beach"
              className="w-full h-full object-cover object-[65%_70%]"
            />
          </div>
        </div>
      </section>

      {/* We build your dream */}
      <section className="py-24 px-6 md:px-12 max-w-[1400px] mx-auto flex flex-col md:flex-row items-center gap-16 lg:gap-32">
        <div className="flex-1 relative">
          <div className="w-full max-w-[500px] aspect-[4/5] rounded-br-[160px] overflow-hidden relative">
            <img src={IMG.ceremony} alt="Outdoor ceremony" className="w-full h-full object-cover" />
          </div>
          <div className="absolute -bottom-12 -right-6 md:-right-12 w-48 aspect-[3/4] rounded-t-full overflow-hidden shadow-2xl border-4 border-background">
            <img src={IMG.details} alt="Details" className="w-full h-full object-cover" />
          </div>
          <GoldSpecks className="-bottom-8 -left-8" />
        </div>
        <div className="flex-1">
          <SectionHeading
            subtitle="We create. We celebrate."
            title="We build your dream"
            italic="around you"
            className="mb-8"
          />
          <p className="text-muted-foreground font-light leading-relaxed max-w-md mb-10 text-[15px]">
            Every couple has a story. Our planners listen first, then design a celebration
            that mirrors who you are — down to the smallest, most personal detail.
          </p>
          <ButtonLink to="/experience" variant="outline">
            Explore
          </ButtonLink>
        </div>
      </section>

      {/* Packages */}
      <section className="py-24 px-6 md:px-12 max-w-[1400px] mx-auto flex flex-col md:flex-row-reverse items-center gap-16 lg:gap-32">
        <div className="flex-1 relative">
          <div className="w-full max-w-[500px] aspect-[4/5] rounded-tl-[160px] overflow-hidden ml-auto relative">
            <img src={IMG.tablescape} alt="Table setting" className="w-full h-full object-cover" />
          </div>
          <div className="absolute top-1/2 -translate-y-1/2 -left-6 md:-left-12 w-48 aspect-[3/4] overflow-hidden shadow-2xl border-4 border-background">
            <img src={IMG.pour} alt="Pouring wine" className="w-full h-full object-cover" />
          </div>
          <GoldSpecks className="-top-8 -right-8" />
        </div>
        <div className="flex-1">
          <SectionHeading
            subtitle="AI Coordination Packages"
            title="We plan your day"
            italic="to perfection"
            className="mb-8"
          />
          <p className="text-muted-foreground font-light leading-relaxed max-w-md mb-10 text-[15px]">
            Three thoughtfully tailored options — choose the level of AI coordinator assistance that fits
            your vision and timeline.
          </p>

          <div className="flex flex-col gap-6 mb-12 max-w-md">
            {[
              { name: "Elite AI Coordinator", desc: "Complete end-to-end management & priority support", price: "€999" },
              { name: "Premium AI Coordinator", desc: "Enhanced review, budget checks & negotiation", price: "€599" },
              { name: "Essential AI Coordinator", desc: "Basic AI sourcing, budget & timeline planning", price: "€299" },
            ].map((pkg) => (
              <div
                key={pkg.name}
                className="flex items-center justify-between border-b border-primary/20 pb-4"
              >
                <div>
                  <h4 className="font-sans font-medium text-sm uppercase tracking-[0.15em]">
                    {pkg.name}
                  </h4>
                  <p className="text-muted-foreground text-[11px] mt-1">{pkg.desc}</p>
                </div>
                <span className="font-serif text-2xl text-primary">{pkg.price}</span>
              </div>
            ))}
          </div>

          <ButtonLink to="/experience" variant="outline">
            Explore
          </ButtonLink>
        </div>
      </section>

      {/* Passion */}
      <section className="py-24 px-6 md:px-12 max-w-[1400px] mx-auto flex flex-col md:flex-row items-center gap-16 lg:gap-32">
        <div className="flex-1 relative">
          <div className="w-full max-w-[500px] aspect-square rounded-br-[200px] overflow-hidden relative">
            <img src={IMG.hands} alt="Couple holding hands rings" className="w-full h-full object-cover" />
          </div>
          <div className="absolute -bottom-16 right-12 md:right-24 w-40 aspect-[3/4] overflow-hidden shadow-2xl border-4 border-background">
            <img src={IMG.aisleOutdoors} alt="Outdoor aisle" className="w-full h-full object-cover" />
          </div>
          <GoldSpecks className="top-1/2 -left-12" />
        </div>
        <div className="flex-1">
          <SectionHeading
            subtitle="It's in the details"
            title="Planning your perfect wedding"
            italic="is our passion"
            className="mb-8"
          />
          <p className="text-muted-foreground font-light leading-relaxed max-w-md mb-10 text-[15px]">
            From the first sketch to the last toast, we sweat the small things so you can
            be fully present for the big ones.
          </p>
          <ButtonLink to="/experience" variant="outline">
            Explore
          </ButtonLink>
        </div>
      </section>

      {/* Gallery */}
      <section id="portfolio" className="py-32 relative">
        <div className="absolute top-0 left-0 w-3/4 md:w-1/2 h-[80%] bg-secondary rounded-br-[200px] -z-10" />

        <div className="max-w-[1400px] mx-auto px-6 md:px-12">
          <SectionHeading
            subtitle="The good beauty"
            title="Our"
            italic="Gallery"
            className="mb-16 md:ml-12"
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-10 items-center mb-16">
            <div className="aspect-[4/3] overflow-hidden">
              <img src={IMG.pour} alt="Gallery 1" className="w-full h-full object-cover hover:scale-105 transition-transform duration-700" />
            </div>
            <div className="aspect-[3/4] overflow-hidden md:-mt-12 shadow-xl">
              <img src={IMG.aisleNight} alt="Gallery 2" className="w-full h-full object-cover hover:scale-105 transition-transform duration-700" />
            </div>
            <div className="aspect-[4/3] overflow-hidden">
              <img src={IMG.details} alt="Gallery 3" className="w-full h-full object-cover hover:scale-105 transition-transform duration-700" />
            </div>
          </div>

          <div className="text-center md:text-left md:ml-12">
            <ButtonLink to="/experience" variant="outline">
              Explore More
            </ButtonLink>
          </div>
        </div>
      </section>

      {/* Event True Master teaser */}
      <section className="py-24 px-6 md:px-12 max-w-[1400px] mx-auto flex flex-col md:flex-row items-center gap-16 lg:gap-32">
        <div className="flex-1">
          <SectionHeading
            subtitle="Wedding plan love"
            title="Event"
            italic="True Master"
            className="mb-8"
          />
          <p className="text-muted-foreground font-light leading-relaxed max-w-md mb-6 text-[15px]">
            Meet the team behind every detail. With over a decade of refined craftsmanship,
            our true masters orchestrate weddings that feel timeless and singular.
          </p>
          <p className="text-muted-foreground font-light leading-relaxed max-w-md mb-10 text-[15px]">
            Step into our world — explore the full experience, menus, and showroom.
          </p>
          <ButtonLink to="/experience" variant="solid">
            Explore the Experience
          </ButtonLink>
        </div>
        <div className="flex-1 relative flex justify-end">
          <div className="w-full max-w-[450px] aspect-square rounded-full overflow-hidden relative p-4 border border-primary/20">
            <div className="w-full h-full rounded-full overflow-hidden">
              <img src={IMG.bouquet} alt="Bride holding bouquet" className="w-full h-full object-cover" />
            </div>
          </div>
          <GoldSpecks className="bottom-0 left-10" />
        </div>
      </section>

      {/* Contact */}
      <section
        id="contact"
        className="py-24 px-6 md:px-12 max-w-[1400px] mx-auto flex flex-col md:flex-row items-start gap-16 lg:gap-32"
      >
        <div className="flex-1 relative">
          <div className="w-full max-w-[550px] aspect-square rounded-br-[250px] overflow-hidden relative">
            <img src={IMG.longCatering} alt="Long catering table" className="w-full h-full object-cover" />
          </div>
          <GoldSpecks className="-bottom-6 -right-6" />
        </div>
        <div className="flex-1 w-full pt-10">
          <SectionHeading
            subtitle="Share us the details"
            title="We'll plan your day,"
            italic="your way."
            className="mb-12"
          />

          <form className="flex flex-col gap-8 max-w-lg">
            <input
              type="text"
              placeholder="My Name"
              className="bg-transparent border-b border-muted-foreground/30 pb-3 text-sm font-sans placeholder:text-muted-foreground/70 focus:outline-none focus:border-primary transition-colors"
            />
            <input
              type="email"
              placeholder="My Email"
              className="bg-transparent border-b border-muted-foreground/30 pb-3 text-sm font-sans placeholder:text-muted-foreground/70 focus:outline-none focus:border-primary transition-colors"
            />
            <input
              type="tel"
              placeholder="My Phone"
              className="bg-transparent border-b border-muted-foreground/30 pb-3 text-sm font-sans placeholder:text-muted-foreground/70 focus:outline-none focus:border-primary transition-colors"
            />
            <select
              defaultValue=""
              className="bg-transparent border-b border-muted-foreground/30 pb-3 text-sm font-sans text-muted-foreground/70 focus:outline-none focus:border-primary transition-colors appearance-none cursor-pointer"
            >
              <option value="" disabled>
                Wedding Details
              </option>
              <option value="planning">Full Planning</option>
              <option value="design">Event Design</option>
              <option value="dayof">Day-of Coordination</option>
            </select>
            <div className="pt-4">
              <button
                type="submit"
                className="inline-flex items-center justify-center font-sans uppercase tracking-[0.2em] text-[11px] font-medium border border-foreground/20 text-foreground hover:border-foreground hover:bg-foreground hover:text-background px-8 py-3 rounded-full transition-all duration-300"
              >
                Submit
              </button>
            </div>
          </form>
        </div>
      </section>

      {/* Blog */}
      <section id="blog" className="py-24 px-6 md:px-12 max-w-[1400px] mx-auto">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-8 mb-16">
          <SectionHeading
            subtitle="Always alert"
            title="Only the good news,"
            italic="only for you"
            className="max-w-lg"
          />
          <ReadMoreLink text="View All" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
          {[
            {
              date: "September 15, 2024",
              title: "10 tips for planning the perfect summer wedding",
              image: IMG.blogSummer,
            },
            {
              date: "September 12, 2024",
              title: "Benefits of hiring an expert wedding planner",
            },
            {
              date: "September 9, 2024",
              title: "Top details brides forget — and how to handle them",
            },
          ].map((post, i) => (
            <div key={i} className="group cursor-pointer">
              {post.image && (
                <div className="aspect-[16/10] overflow-hidden rounded-t-[100px] mb-6">
                  <img
                    src={post.image}
                    alt={post.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                  />
                </div>
              )}
              <div className={post.image ? "flex flex-col" : "flex flex-col pt-6 md:pt-0"}>
                <span className="font-sans text-[11px] text-muted-foreground uppercase tracking-[0.2em] mb-3">
                  {post.date}
                </span>
                <h4 className="font-serif text-2xl text-foreground leading-snug mb-4 group-hover:text-primary transition-colors font-light">
                  {post.title}
                </h4>
                <span className="font-sans text-[11px] uppercase tracking-[0.2em] text-primary flex items-center gap-2">
                  Read More <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                </span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
