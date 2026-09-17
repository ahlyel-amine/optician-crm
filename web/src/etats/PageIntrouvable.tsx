import { Link } from "react-router-dom";

import { LIEN_VERS_LE_TABLEAU_DE_BORD, MESSAGE_PAGE_INEXISTANTE } from "./messages";

/**
 * 404 — la phrase, et une issue. Une impasse sans lien est un cul-de-sac.
 *
 * Ce n'est PAS un repere `main` : depuis le plan 03-13 cette page se rend dans
 * la zone de contenu du shell, qui est deja le `main` unique. Deux `main`
 * imbriques cassent le contrat de reperes de 03-UI-SPEC.md section 10.
 */
export function PageIntrouvable() {
  return (
    <div className="mx-auto max-w-prose py-6">
      <h1 className="text-2xl font-semibold">{MESSAGE_PAGE_INEXISTANTE}</h1>
      <p className="mt-4 text-sm">
        <Link className="underline" to="/">
          {LIEN_VERS_LE_TABLEAU_DE_BORD}
        </Link>
      </p>
    </div>
  );
}
