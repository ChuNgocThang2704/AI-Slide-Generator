// The slide editor's copy buffer, shared by every slide canvas in the page (so an element
// copied on one slide can be pasted on another). Lives in its own module because it is
// mutable state that outlives any one canvas.
let items = null;

export const getClipboard = () => items;
export const setClipboard = (list) => { items = list; };
