import { BrowserRouter, Routes, Route } from "react-router";
import { Layout } from "./design-system/Layout";
import { Landing } from "./views/Landing";
import { Experience } from "./views/Experience";

const basename = import.meta.env.BASE_URL.replace(/\/$/, "") || "/";

export default function App() {
  return (
    <BrowserRouter basename={basename}>
      <Layout>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/experience" element={<Experience />} />
          <Route path="*" element={<Landing />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
