function buildImageFactory(imageData) {
    "use strict";
    const data = imageData.data,
        width = imageData.width,
        maxArea = imageData.width * imageData.height;

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
            let average;
            return {
                x1, y1, x2, y2,
                getHeight() {
                    return (x2 - x1) * (y2 - y1) / maxArea;
                },
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
                    if (!average) {
                        let r=0,g=0,b=0,count=0;
                        forEach(p => {
                            r += p[0];
                            g += p[1];
                            b += p[2];
                            count++;
                        });
                        average = [r/count,g/count,b/count];
                    }
                    return average;
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

const canvas = document.getElementById('canvas');
const video = document.getElementById('video');
const ctx = canvas.getContext('2d');
let width, height;

video.addEventListener('play', function() {
    width = self.video.videoWidth * 2;
    height = self.video.videoHeight * 2;
    const hiddenCanvas = document.createElement('canvas');
    canvas.width = hiddenCanvas.width = width;
    canvas.height = hiddenCanvas.height = height;
    const hiddenCtx = hiddenCanvas.getContext('2d');

    function computeFrame() {
        hiddenCtx.drawImage(video, 0, 0, width, height);
        let frame = hiddenCtx.getImageData(0, 0, width, height);
        draw(frame);
    }

    function timerCallback() {
        if (video.paused || video.ended) {
            return;
        }
        computeFrame();
        setTimeout(() => {
            timerCallback();
        }, 0);
    }

    timerCallback();
}, false);

function draw(imageData) {
    "use strict";
    const factory = buildImageFactory(imageData);

    const VARIANCE_THRESHOLD = 300, queue = [factory.makeImagePiece(0, 0, imageData.width - 1, imageData.height - 1)], finished = [],
        xOffset = 0.25,
        yOffset = 0.25,
        e = Math.pow(1/(1-yOffset),height);

    function processNext() {
        "use strict";
        const nextPiece = queue.shift(),
            variance = nextPiece.getVariance();
        if (variance < VARIANCE_THRESHOLD) {
            finished.push(nextPiece);
        } else {
            const [piece1, piece2] = nextPiece.split();
            queue.push(piece1);
            queue.push(piece2);
        }
    }

    while (queue.length) {
        processNext();
    }

    function distanceFromViewer(p) {
        return Math.pow(height - p.y2, 2) + Math.min(Math.pow(p.x1 - width/2, 2), Math.pow(p.x2 - width/2, 2));
    }
    function sortByDistance(p1, p2) {
        return distanceFromViewer(p2) - distanceFromViewer(p1);
    }
    const d = 1000;
    function transformCoord(x,y,z) {
        return {
            x: x*d/z,
            y: y*d/z
        };
    }
    function rgbToHsl(r, g, b){
        r /= 255, g /= 255, b /= 255;
        var max = Math.max(r, g, b), min = Math.min(r, g, b);
        var h, s, l = (max + min) / 2;

        if(max == min){
            h = s = 0; // achromatic
        }else{
            var d = max - min;
            s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
            switch(max){
                case r: h = (g - b) / d + (g < b ? 6 : 0); break;
                case g: h = (b - r) / d + 2; break;
                case b: h = (r - g) / d + 4; break;
            }
            h /= 6;
        }

        return [h , s, l];
    }
    const tilt = Math.PI / 4;
    function tilt3dCoords(x,y,z) {
        return {
            x,
            y: (z-d) * Math.sin(tilt) + (y + height/2) * Math.cos(tilt) - height/2 ,
            z: (z-d) * Math.cos(tilt) - (y + height/2) * Math.sin(tilt) + d
        };
    }
    function getCanvasCoords(x,y,h) {
        const x3dFlat = x - width/2,
            y3dFlat = h - height/2,
            z3dFlat = d + (height - y),
            tiltedCoords = tilt3dCoords(x3dFlat, y3dFlat, z3dFlat),
            transformedCoords = transformCoord(tiltedCoords.x, tiltedCoords.y, tiltedCoords.z),
            // transformedCoords = transformCoord(x3dFlat, y3dFlat, z3dFlat),
            projectedCoords = {x: transformedCoords.x + width/2, y: -transformedCoords.y + height/2};
        // console.log(`(${x},${y}) -> (${x3dFlat},${y3dFlat},${z3dFlat}) -> (${tiltedCoords.x},${tiltedCoords.y},${tiltedCoords.z}) -> (${projectedCoords.x},${projectedCoords.y})`)

        return [projectedCoords.x, projectedCoords.y];
    }
    function renderPiece(p) {
        const
            h = p.getHeight() * 1000,
            hsl = rgbToHsl(...p.getAverage());

        // Top face
        ctx.fillStyle = `hsl(${hsl[0] * 360},${hsl[1] * 100}%,${hsl[2] * 70}%)`;
        ctx.beginPath();
        ctx.moveTo(...getCanvasCoords(p.x1, p.y1, h));
        ctx.lineTo(...getCanvasCoords(p.x2, p.y1, h));
        ctx.lineTo(...getCanvasCoords(p.x2, p.y2, h));
        ctx.lineTo(...getCanvasCoords(p.x1, p.y2, h));
        ctx.fill();

        // Front face
        ctx.fillStyle = `hsl(${hsl[0] * 360},${hsl[1] * 100}%,${hsl[2] * 40}%)`;
        ctx.beginPath();
        ctx.moveTo(...getCanvasCoords(p.x1, p.y2, 0));
        ctx.lineTo(...getCanvasCoords(p.x1, p.y2, h));
        ctx.lineTo(...getCanvasCoords(p.x2, p.y2, h));
        ctx.lineTo(...getCanvasCoords(p.x2, p.y2, 0));
        ctx.fill();

        // Right face
        if (p.x2 < width/2) {
            ctx.fillStyle = `hsl(${hsl[0] * 360},${hsl[1] * 100}%,${hsl[2] * 40}%)`;
            ctx.beginPath();
            ctx.moveTo(...getCanvasCoords(p.x2, p.y2, 0));
            ctx.lineTo(...getCanvasCoords(p.x2, p.y2, h));
            ctx.lineTo(...getCanvasCoords(p.x2, p.y1, h));
            ctx.lineTo(...getCanvasCoords(p.x2, p.y1, 0));
            ctx.fill();
        }

        // Left face
        if (p.x1 > width/2) {
            ctx.beginPath();
            ctx.fillStyle = `hsl(${hsl[0] * 360},${hsl[1] * 100}%,${hsl[2] * 100}%)`;
            ctx.moveTo(...getCanvasCoords(p.x1, p.y2, 0));
            ctx.lineTo(...getCanvasCoords(p.x1, p.y2, h));
            ctx.lineTo(...getCanvasCoords(p.x1, p.y1, h));
            ctx.lineTo(...getCanvasCoords(p.x1, p.y1, 0));
            ctx.fill();
        }

    }
    ctx.clearRect(0,0,width, height);
    finished.sort(sortByDistance).forEach(renderPiece);
}

