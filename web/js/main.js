const img = new Image();


function buildImageFactory(imageData) {
    "use strict";
    const data = imageData.data,
        width = imageData.width;

    function getPixel(x,y) {
        const redIndex = (width * 4 * y) + (x * 4),
            greenIndex = redIndex + 1,
            blueIndex = greenIndex + 1;
        return [data[redIndex], data[greenIndex], data[blueIndex]];
    }

    const factory = {
        makeImagePiece(x1, y1, x2, y2) {
            function forEach(fn) {
                for (let x = x1; x <= x2; x++) {
                    for (let y = y1; y <= y2; y++) {
                        fn(getPixel(x,y));
                    }
                }
            }
            return {
                x1, y1, x2, y2,
                getVariance() {
                    if (x2 - x1 < 5 || y2 - y1 < 5) {
                        return 0;
                    }
                    let min = Number.MAX_VALUE,
                        max = Number.MIN_VALUE;
                    forEach(p => {
                        const v = p[0] + p[1] + p[2];
                        min = Math.min(min, v);
                        max = Math.max(max, v);
                    });
                    return max - min;
                },
                getAverage() {
                    let r=0,g=0,b=0,count=0;
                    forEach(p => {
                        r += p[0];
                        g += p[1];
                        b += p[2];
                        count++;
                    });
                    return [r/count,g/count,b/count];
                },
                split() {
                    const xDiff = x2 - x1,
                        yDiff = y2 - y1;
                    if (xDiff < yDiff) {
                        const ySplit = Math.round((y1 + y2) / 2),
                            topPiece = factory.makeImagePiece(x1, y1, x2, ySplit),
                            bottomPiece = factory.makeImagePiece(x1, ySplit+1, x2, y2);
                        return [topPiece , bottomPiece];
                    } else {
                        const xSplit = Math.round((x1 + x2) / 2),
                            leftPiece = factory.makeImagePiece(x1, y1, xSplit, y2),
                            rightPiece = factory.makeImagePiece(xSplit+1, y1, x2, y2);
                        return [leftPiece , rightPiece];
                    }
                }
            };
        }
    };
    return factory;
}

const status = document.getElementById('status');
img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d');
    ctx.strokeStyle='red';
    ctx.drawImage(img,0,0);
    const imageData = ctx.getImageData(0, 0, img.width, img.height),
        factory = buildImageFactory(imageData);
    document.body.appendChild(canvas)

    const VARIANCE_THRESHOLD = 100, queue = [factory.makeImagePiece(0,0,img.width-1, img.height-1)], finished = [];
    const tStart = Date.now();
    function processNext() {
        "use strict";
        const nextPiece = queue.shift(),
            variance = nextPiece.getVariance();
        if (variance < VARIANCE_THRESHOLD) {
            finished.push(nextPiece);
            const avg = nextPiece.getAverage();
            ctx.beginPath();
            ctx.fillStyle = `rgb(${Math.round(avg[0])},${Math.round(avg[1])},${Math.round(avg[2])})`;
            ctx.strokeStyle = 'black'
            ctx.fillRect(nextPiece.x1, nextPiece.y1, (nextPiece.x2 - nextPiece.x1 + 1), (nextPiece.y2 - nextPiece.y1 + 1))
            ctx.rect(nextPiece.x1, nextPiece.y1, (nextPiece.x2 - nextPiece.x1 + 1), (nextPiece.y2 - nextPiece.y1 + 1))
            ctx.stroke();
        } else {
            const [piece1, piece2] = nextPiece.split();
            queue.push(piece1);
            queue.push(piece2);
        }
        if (queue.length) {
            status.innerText = queue.length;

        } else {
            status.innerText = (Date.now() - tStart) / 1000;
        }
    }
    while(queue.length) {
        processNext();
    }

};
img.src = './test.png';

