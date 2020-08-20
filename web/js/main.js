const img = new Image();

function makeImage(imageData) {
    "use strict";
    const data = imageData.data,
        width = imageData.width;
    return {
        getPixel(x,y) {
            const redIndex = (width * 4 * y) + (x * 4),
                greenIndex = redIndex + 1,
                blueIndex = greenIndex + 1;
            return [data[redIndex], data[greenIndex], data[blueIndex]];
        }
    };
}
img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img,0,0);
    const imageData = ctx.getImageData(0, 0, img.width-1, img.height-1),
        image = makeImage(imageData);
};
img.src = './test.png';

