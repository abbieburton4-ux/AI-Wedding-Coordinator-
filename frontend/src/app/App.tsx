import { BrowserRouter, Routes, Route } from "react-router";
import { Layout } from "./design-system/Layout";
import { Landing } from "./views/Landing";
import { Experience } from "./views/Experience";

export default function App() {
  return (
    <BrowserRouter>
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
