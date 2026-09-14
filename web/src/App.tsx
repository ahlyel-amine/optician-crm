/**
 * Squelette minimal.
 *
 * Le shell reel — barre superieure, selecteur de magasin, navigation filtree par
 * les droits, recherche — arrive au plan 03-13. Ce composant existe pour que
 * `vite build` ait un point d'entree et pour que le proxy meme-origine du
 * serveur de developpement soit verifiable a l'oeil.
 */
export default function App() {
  return (
    <main>
      <h1>Optique</h1>
      <p>
        Le shell de l'application est construit au plan 03-13. Cette page
        n'existe que pour verifier la construction et le proxy meme-origine.
      </p>
    </main>
  );
}
