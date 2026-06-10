// Encolhe uma imagem escolhida pelo usuário, no NAVEGADOR, para caber em max×max
// (preservando a proporção) e devolve um data URI PNG — pequeno o bastante para
// guardar no banco como texto. Usado no logo da organização.

export async function lerImagemRedimensionada(
  file: File,
  max = 128,
): Promise<string> {
  if (!file.type.startsWith("image/")) {
    throw new Error("Selecione um arquivo de imagem.");
  }
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => reject(new Error("Não consegui ler a imagem."));
      im.src = url;
    });
    const escala = Math.min(1, max / Math.max(img.width, img.height));
    const largura = Math.max(1, Math.round(img.width * escala));
    const altura = Math.max(1, Math.round(img.height * escala));

    const canvas = document.createElement("canvas");
    canvas.width = largura;
    canvas.height = altura;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Não consegui processar a imagem.");
    ctx.drawImage(img, 0, 0, largura, altura);
    return canvas.toDataURL("image/png");
  } finally {
    URL.revokeObjectURL(url);
  }
}
