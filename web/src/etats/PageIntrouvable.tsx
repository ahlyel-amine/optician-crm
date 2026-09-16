import { Link } from "react-router-dom";

import { LIEN_VERS_LE_TABLEAU_DE_BORD, MESSAGE_PAGE_INEXISTANTE } from "./messages";

/** 404 — la phrase, et une issue. Une impasse sans lien est un cul-de-sac. */
export function PageIntrouvable() {
  return (
    <main className="mx-auto max-w-prose px-6 py-12">
      <h1 className="text-2xl font-semibold">{MESSAGE_PAGE_INEXISTANTE}</h1>
      <p className="mt-4 text-sm">
        <Link className="underline" to="/">
          {LIEN_VERS_LE_TABLEAU_DE_BORD}
        </Link>
      </p>
    </main>
  );
}
