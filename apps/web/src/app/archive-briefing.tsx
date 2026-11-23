import Image from "next/image";
import CaliforniaDemo from "./landing-demo/california-demo";
import styles from "./archive-briefing.module.css";
import landingStyles from "./landing.module.css";

const platforms = [
  {
    icon: "openai-chatgpt",
    name: "OpenAI Data Agent",
    href: "https://openai.com/index/put-data-to-work/",
    focus: "Investigación conversacional y dashboards interactivos.",
    application: "La pregunta abre un recorrido entre el gráfico y los informes del mapa.",
  },
  {
    icon: "claude",
    name: "Claude Data y Dashboards",
    href: "https://support.claude.com/en/articles/17454700-get-started-with-claude-data",
    focus: "Consulta de fuentes conectadas e historias visuales.",
    application: "El agente elige la visualización según la pregunta.",
  },
  {
    icon: "databricks",
    name: "Databricks Genie Agents",
    href: "https://docs.databricks.com/aws/en/genie-agents/",
    focus: "Analítica en lenguaje natural sobre datos gobernados por Unity Catalog.",
    application: "Cada análisis sigue criterios definidos para seleccionar los registros.",
  },
  {
    icon: "tableau",
    name: "Tableau Knowledge",
    href: "https://help.tableau.com/current/online/en-gb/tableau_knowledge_about.htm",
    focus: "Contexto semántico y definiciones de negocio para agentes.",
    application: "Contamos cada informe como un registro y documentamos los posibles duplicados.",
  },
];

export default function ArchiveBriefing() {
  return (
    <section className={styles.briefing} id="metodo" aria-labelledby="method-title">
      <div className={styles.inner}>
        <div className={styles.intro}>
          <h2 className={landingStyles.sectionTitle} id="method-title">Cómo funciona</h2>
          <blockquote>“Muéstrame los reportes de 1990 en California”</blockquote>
        </div>
        <CaliforniaDemo />
        <details className={styles.references} id="plataformas">
          <summary>Referencias empresariales</summary>
          <p>Cuatro enfoques que estudiamos para conectar preguntas, visualizaciones y reglas de datos.</p>
          <div className={styles.platformHead} aria-hidden="true">
            <span>Plataforma</span><span>Qué estudiamos</span><span>En UFO Data Agent</span>
          </div>
          <ul className={styles.platforms} aria-label="Plataformas de Data Agents Research">
            {platforms.map(({ icon, name, href, focus, application }) => (
              <li key={name}>
                <a href={href} className={styles.platformName}>
                  <Image src={`/archivo-uap/plataformas/${icon}.svg`} width={36} height={36} alt="" />
                  {name}
                </a>
                <p>{focus}</p>
                <p><span className="sr-only">Aplicación en UFO Data Agent. </span>{application}</p>
              </li>
            ))}
          </ul>
          <a className={styles.researchLink} href="https://github.com/marcor0311/data-agents-research#plataformas-de-referencia">
            Ver la comparación en Data Agents Research
          </a>
        </details>
      </div>
    </section>
  );
}
