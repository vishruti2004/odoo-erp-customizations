export function loadFont(fontName) {
    if (!fontName) {
        return;
    }
    const family = String(fontName).replace(/_/g, " ").replace(/[^\w\s-]/g, "");
    const id = `pcl-font-${family.replace(/\s+/g, "-")}`;
    if (document.getElementById(id)) {
        return;
    }
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = `https://fonts.googleapis.com/css2?family=${family.replace(/\s+/g, "+")}:wght@400;500;700&display=swap`;
    document.head.appendChild(link);
}
