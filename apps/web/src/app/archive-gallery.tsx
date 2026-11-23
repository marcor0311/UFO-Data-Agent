import Image from "next/image";
import archivePhoto from "../../public/archivo-uap/mesa-de-archivo.webp";
import styles from "./landing.module.css";

export default function ArchiveGallery() {
  return (
    <section className={styles.archive} id="archivo" aria-labelledby="archive-title">
      <div className={styles.archiveText}>
        <h2 className={styles.sectionTitle} id="archive-title">El archivo</h2>
        <dl>
          <div>
            <dt>El problema</dt>
            <dd>Los informes UAP están dispersos en archivos con criterios distintos, lo que dificulta compararlos.</dd>
          </div>
          <div>
            <dt>La solución</dt>
            <dd>
              Un agente de datos con analítica conversacional para investigar casos UAP y explorar más de 700.000 reportes.
            </dd>
          </div>
        </dl>
      </div>
      <figure className={styles.archivePhoto}>
        <Image
          src={archivePhoto}
          alt="Carpeta de archivo sobre un mapa topográfico y una tira de negativos"
          sizes="(max-width: 760px) 92vw, (max-width: 1460px) 49vw, 700px"
        />
      </figure>
    </section>
  );
}
