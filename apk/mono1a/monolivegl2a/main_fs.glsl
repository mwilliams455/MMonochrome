#extension GL_OES_EGL_image_external_essl3 : require
precision highp float;
precision highp int;
// MONOLIVEGL2A_CONTROLLEDOES: SOURCE1D Y + exact frozen Monochrom curve02, no fitted residual.
uniform highp samplerExternalOES sTexture;
uniform highp sampler2D uMonoInverse2A;
uniform highp sampler2D uMonoCurve2A;
uniform bool uMonoSourceReady2A;
uniform bool uMonoProbe2A;
uniform mat3 uMonoInputToSensor2A;
uniform vec3 uMonoSourceY2A;
uniform float uMonoExposureScale1A;
uniform vec2 resolution;
uniform bool enablePeak;
uniform bool mirror;
in vec2 texCoord;
out vec4 Output;
float inverseChannel(float s, int c) {
    // Reconstruct integer table nodes before interpolation. Hardware bilinear
    // filtering of packed high/low bytes can differ by multiple output codes.
    float p=clamp(s,0.0,1.0)*1023.0;
    int i=int(floor(p)), j=min(i+1,1023);
    vec3 a=(texelFetch(uMonoInverse2A,ivec2(i,0),0).rgb*256.0+
            texelFetch(uMonoInverse2A,ivec2(i,1),0).rgb)*(255.0/65535.0);
    vec3 b=(texelFetch(uMonoInverse2A,ivec2(j,0),0).rgb*256.0+
            texelFetch(uMonoInverse2A,ivec2(j,1),0).rgb)*(255.0/65535.0);
    return mix(a[c],b[c],p-float(i));
}
vec3 srgbLinear(vec3 c) {
    return mix(c/12.92,pow((c+0.055)/1.055,vec3(2.4)),step(vec3(0.04045),c));
}
float srgbCode(float x) {
    return x<=0.0031308 ? 12.92*x : 1.055*pow(x,1.0/2.4)-0.055;
}
float monochrome(vec3 oes) {
    if (!uMonoSourceReady2A) {
        // Explicit approximate fallback; never apply sensor transforms to unchecked OES.
        return clamp(srgbCode(dot(srgbLinear(clamp(oes,0.0,1.0))*uMonoExposureScale1A,
                vec3(0.2126,0.7152,0.0722))),0.0,1.0);
    }
    vec3 linearRgb=vec3(inverseChannel(oes.r,0),inverseChannel(oes.g,1),inverseChannel(oes.b,2));
    vec3 sensor=uMonoInputToSensor2A*linearRgb;
    // ISP shading/demosaic are already present. Do not apply another RAW LensShadingMap.
    // Match the still weighted-kernel coordinate: uint16 camRGB -> rounded uint16 Y -> >>5.
    vec3 cam16=floor(clamp(sensor*uMonoExposureScale1A,0.0,1.0)*65535.0+0.5);
    float source16=floor(clamp(dot(cam16,uMonoSourceY2A),0.0,65535.0)+0.5);
    int index=int(source16)>>5;
    return texelFetch(uMonoCurve2A,ivec2(index,0),0).r;
}
void main() {
    vec2 uv=texCoord;
    if (mirror) uv.y=1.0-uv.y;
    vec4 oes=texture(sTexture,uv);
    float y=monochrome(oes.rgb);
    // One small FBO pass packs pre-transform RGB and target Y from the SAME source texture.
    // Not a screenshot of the display compositor and not sampled RAW.
    if (uMonoProbe2A) { Output=vec4(oes.rgb,y); return; }
    vec4 color=vec4(vec3(y),1.0);
    if (enablePeak) {
        vec4 avg=vec4(0);
        for(int i=-1;i<=1;i++) for(int j=-1;j<=1;j++)
            avg+=texture(sTexture,uv+vec2(i*2,j*2)/resolution);
        avg/=9.0;
        float diff=dot(abs(oes-avg),vec4(0.299,0.587,0.114,0));
        float w=diff*diff/(0.05+diff*diff);
        color+=vec4(1,0,1,0)*32.0*diff*w;
    }
    Output=color;
}
